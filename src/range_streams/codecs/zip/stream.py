from __future__ import annotations

import struct

from ranges import Range

from ...range_stream import RangeStream
from .data import ZipData

__all__ = ["ZipStream"]


class ZipStream(RangeStream):
    def __init__(
        self,
        url: str,
        client=None,
        byte_range: Range | tuple[int, int] = Range("[0, 0)"),
        pruning_level: int = 0,
    ):
        super().__init__(
            url=url, client=client, byte_range=byte_range, pruning_level=pruning_level
        )
        self.data = ZipData()

    def check_head_bytes(self):
        start_sig = self.data.LOC_F_H.start_sig
        head_byte_range = Range(0, len(start_sig))
        self.add(head_byte_range)
        start_bytes = self.active_range_response.read()
        if start_bytes != start_sig:
            # Actually think this will be if zip is empty? Test...
            raise ValueError(
                f"Invalid zip header sequence {start_bytes=!r}: expected {start_sig!r}"
            )

    def check_end_of_central_dir_start(self):
        """
        If the zip file lacks a comment, the End Of Central Directory Record will be the
        last thing in it, so taking the range equal to its expected size and checking
        for the expected start signature will find it.
        """
        eocd_rng = self.total_range
        eocd_rng.start = eocd_rng.end - self.data.E_O_CTRL_DIR_REC.get_size()
        self.add(eocd_rng)
        eocd_bytes = self.active_range_response.read()
        start_sig = self.data.E_O_CTRL_DIR_REC.start_sig
        start_found = eocd_bytes[: len(start_sig)] == start_sig
        no_comment = eocd_bytes[-2:] == b"\000\000"
        if start_found and no_comment:
            self.data.E_O_CTRL_DIR_REC.start_pos = eocd_rng.start
        else:
            # self.search_back_to_end_of_central_dir()
            raise NotImplementedError("Brute force search is deprecated")

    def check_end_of_central_dir_rec(self):
        """
        Using the stored start position of the End Of Central Directory Record
        (or calculating and storing it if it is not yet set on the object),
        """
        if self.data.E_O_CTRL_DIR_REC.start_pos is None:
            self.check_end_of_central_dir_start()
        eocd_rng = self.total_range
        eocd_rng.start = self.data.E_O_CTRL_DIR_REC.start_pos
        self.add(eocd_rng)
        b = self.active_range_response.read()[: self.data.E_O_CTRL_DIR_REC.get_size()]
        u = struct.unpack(self.data.E_O_CTRL_DIR_REC.struct, b)
        _ECD_ENTRIES_TOTAL = 4
        _ECD_SIZE = 5
        _ECD_OFFSET = 6
        self.data.CTRL_DIR_REC.entry_count = u[_ECD_ENTRIES_TOTAL]
        self.data.CTRL_DIR_REC.size = u[_ECD_SIZE]
        self.data.CTRL_DIR_REC.start_pos = u[_ECD_OFFSET]
        return

    def check_central_dir_rec(self):
        """
        Read the range corresponding to the Central Directory Record
        (after :meth:`check_end_of_central_dir_rec` has been called).
        """
        if self.data.CTRL_DIR_REC.size is None:
            self.check_end_of_central_dir_rec()
        size_cd_full = self.data.CTRL_DIR_REC.size  # total size of CDR (all entries)
        cd_read_offset = 0  # byte offset incremented after each entry
        print(f"{self.data.CTRL_DIR_REC.entry_count=}")
        self.zipped_files = []
        entry_range = range(self.data.CTRL_DIR_REC.entry_count)  # type: ignore
        for entry_i in entry_range:
            cd_start = self.data.CTRL_DIR_REC.start_pos + cd_read_offset  # type: ignore
            cd_size = self.data.CTRL_DIR_REC.get_size()
            cd_end = cd_start + cd_size
            cd_rng = Range(cd_start, cd_end)
            self.add(cd_rng)
            cd_bytes = self.active_range_response.read()
            u = struct.unpack(self.data.CTRL_DIR_REC.struct, cd_bytes[:cd_size])
            print(u)
            zf_info = ZippedFileInfo.from_central_directory_entry(u)
            target = self.data.CTRL_DIR_REC.start_sig
            sig = zf_info.signature
            if sig != target:
                raise ValueError(f"Bad Central Directory signature at {cd_start}")
            fn_len = zf_info.filename_length
            fn_rng = Range(cd_end, cd_end + fn_len)
            self.add(fn_rng)
            filename = self.active_range_response.read()
            flags = zf_info.flags
            if flags & 0x800:
                # UTF-8 file names extension
                filename = filename.decode("utf-8")
            else:
                # Historical ZIP filename encoding
                filename = filename.decode("cp437")
            print(filename)
            extra_len = zf_info.extra_field_length
            comment_len = zf_info.comment_length
            cd_read_offset += cd_size + fn_len + extra_len + comment_len
            zf_info = ZippedFileInfo.from_central_directory_entry(u, filename=filename)
            self.zipped_files.append(zf_info)
        return

    # def foo(self):
    #    centdir = fp.read(sizeCentralDir)
    #    if len(centdir) != sizeCentralDir:
    #        raise BadZipFile("Truncated central directory")
    #    centdir = struct.unpack(structCentralDir, centdir)
    #    if centdir[_CD_SIGNATURE] != stringCentralDir:
    #        raise BadZipFile("Bad magic number for central directory")
    #    if self.debug > 2:
    #        print(centdir)
    #    filename = fp.read(centdir[_CD_FILENAME_LENGTH])
    #    flags = centdir[5]
    #    if flags & 0x800:
    #        # UTF-8 file names extension
    #        filename = filename.decode("utf-8")
    #    else:
    #        # Historical ZIP filename encoding
    #        filename = filename.decode("cp437")
    #    # Create ZipInfo instance to store file information
    #    x = ZipInfo(filename)
    #    x.extra = fp.read(centdir[_CD_EXTRA_FIELD_LENGTH])
    #    x.comment = fp.read(centdir[_CD_COMMENT_LENGTH])
    #    x.header_offset = centdir[_CD_LOCAL_HEADER_OFFSET]
    #    (
    #        x.create_version,
    #        x.create_system,
    #        x.extract_version,
    #        x.reserved,
    #        x.flag_bits,
    #        x.compress_type,
    #        t,
    #        d,
    #        x.CRC,
    #        x.compress_size,
    #        x.file_size,
    #    ) = centdir[1:12]
    #    if x.extract_version > MAX_EXTRACT_VERSION:
    #        raise NotImplementedError(
    #            "zip file version %.1f" % (x.extract_version / 10)
    #        )
    #    x.volume, x.internal_attr, x.external_attr = centdir[15:18]
    #    # Convert date/time code to (year, month, day, hour, min, sec)
    #    x._raw_time = t
    #    x.date_time = (
    #        (d >> 9) + 1980,
    #        (d >> 5) & 0xF,
    #        d & 0x1F,
    #        t >> 11,
    #        (t >> 5) & 0x3F,
    #        (t & 0x1F) * 2,
    #    )
    #
    #    x._decodeExtra()
    #    x.header_offset = x.header_offset + concat
    #    self.filelist.append(x)
    #    self.NameToInfo[x.filename] = x
    #
    #    # update total bytes read from central directory
    #    total = (
    #        total
    #        + sizeCentralDir
    #        + centdir[_CD_FILENAME_LENGTH]
    #        + centdir[_CD_EXTRA_FIELD_LENGTH]
    #        + centdir[_CD_COMMENT_LENGTH]
    #    )

    def get_central_dir_bytes(self, step=20):
        """
        Using the stored start position of the End Of Central Directory Record
        (or calculating and storing it if it is not yet set on the object),
        identify the files in the central directory record by searching backwards
        from the start of the End of Central Directory Record signature until
        finding the start of the Central Directory Record.
        """
        if self.data.E_O_CTRL_DIR_REC.start_pos is None:
            self.check_end_of_central_dir_rec()
        pre_eocd = self.data.E_O_CTRL_DIR_REC.start_pos
        cent_dir_rng = Range(pre_eocd - step, pre_eocd)
        self.add(cent_dir_rng)
        target = self.data.CTRL_DIR_REC.start_sig
        byte_cache = b""
        cd_byte_store = b""
        cache_miss_size = len(target) - 1
        while cent_dir_rng.start > 0:
            self.add(cent_dir_rng)
            cd_bytes = self.active_range_response.read()
            cd_byte_store = cd_bytes + cd_byte_store
            byte_cache = cd_bytes + byte_cache[:cache_miss_size]
            if target in byte_cache:
                offset = byte_cache.find(target)
                self.data.CTRL_DIR_REC.start_pos = cent_dir_rng.start + offset
                break
            else:
                cent_dir_rng.start -= step
                cent_dir_rng.end -= step
        else:
            raise ValueError(f"No central directory start signature found")
        # cent_dir_rng.end = self.data.E_O_CTRL_DIR_REC.start_pos
        cd_byte_store = cd_byte_store[offset:]
        return cd_byte_store

    def get_central_dir_files(self, step=20) -> list[tuple[bytes, bytes]]:
        """
        Parse the central directory bytes into a list of files.
        """
        cdr_bytes = self.get_central_dir_bytes(step=step)
        cdr_size = self.data.CTRL_DIR_REC.get_size()
        cdr_bytes, cdr_post_bytes = cdr_bytes[:cdr_size], cdr_bytes[cdr_size:]
        cdr_rec = struct.unpack(self.data.CTRL_DIR_REC.struct, cdr_bytes)
        _CD_FILENAME_LENGTH = 12
        _CD_EXTRA_FIELD_LENGTH = 13
        cdr_fn_len = cdr_rec[_CD_FILENAME_LENGTH]
        cdr_extra_field_len = cdr_rec[_CD_EXTRA_FIELD_LENGTH]
        cdr_fn = cdr_post_bytes[:cdr_fn_len]
        cdr_extra = cdr_post_bytes[cdr_fn_len : cdr_fn_len + cdr_extra_field_len]
        cdr_files = [(cdr_fn, cdr_extra)]
        return cdr_files

    @property
    def file_list(self) -> list[bytes]:
        """
        Return only the file name list from the stored list of 2-tuples
        of (filename, extra bytes).
        """
        if not hasattr(self, "_file_list"):
            self._file_info_list = self.get_central_dir_files()
        return [fn for fn, extra in self._file_info_list]


class CentralDirectoryInfo:
    _CD_SIGNATURE = 0
    _CD_FLAG_BITS = 5
    _CD_COMPRESS_TYPE = 6
    _CD_COMPRESSED_SIZE = 10
    _CD_UNCOMPRESSED_SIZE = 11
    _CD_FILENAME_LENGTH = 12
    _CD_EXTRA_FIELD_LENGTH = 13
    _CD_COMMENT_LENGTH = 14
    _CD_LOCAL_HEADER_OFFSET = 18


class ZippedFileInfo(CentralDirectoryInfo):
    def __init__(
        self,
        signature: bytes | int,
        flags: bytes | int,
        compress_type: bytes | int,
        compressed_size: bytes | int,
        uncompressed_size: bytes | int,
        filename_length: bytes | int,
        extra_field_length: bytes | int,
        comment_length: bytes | int,
        local_header_offset: bytes | int,
        filename: str | None,
    ):
        self.signature = signature
        self.flags = flags
        self.compress_type = compress_type
        self.compressed_size = compressed_size
        self.uncompressed_size = uncompressed_size
        self.filename_length = filename_length
        self.extra_field_length = extra_field_length
        self.comment_length = comment_length
        self.local_header_offset = local_header_offset
        self.filename = filename

    def __repr__(self):
        return (
            f"{self.__class__.__name__}"
            f" '{self.filename if self.filename is not None else ''}'"
            f" @ {self.local_header_offset!r}: {self.compressed_size!r}B"
        )

    @classmethod
    def from_central_directory_entry(
        cls,
        cd_entry,  # : tuple[bytes, int, int, int, int, int, int, int, int]
        filename: str | None = None,
    ):
        signature = cd_entry[cls._CD_SIGNATURE]
        flags = cd_entry[cls._CD_FLAG_BITS]
        compress_type = cd_entry[cls._CD_COMPRESS_TYPE]
        compressed_size = cd_entry[cls._CD_COMPRESSED_SIZE]
        uncompressed_size = cd_entry[cls._CD_UNCOMPRESSED_SIZE]
        filename_length = cd_entry[cls._CD_FILENAME_LENGTH]
        extra_field_length = cd_entry[cls._CD_EXTRA_FIELD_LENGTH]
        comment_length = cd_entry[cls._CD_COMMENT_LENGTH]
        local_header_offset = cd_entry[cls._CD_LOCAL_HEADER_OFFSET]
        return cls(
            signature=signature,
            flags=flags,
            compress_type=compress_type,
            compressed_size=compressed_size,
            uncompressed_size=uncompressed_size,
            filename_length=filename_length,
            extra_field_length=extra_field_length,
            comment_length=comment_length,
            local_header_offset=local_header_offset,
            filename=filename,
        )
