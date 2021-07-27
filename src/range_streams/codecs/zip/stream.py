from __future__ import annotations

import io
import struct

from pyzstd import ZstdFile
from ranges import Range

from ...range_stream import RangeStream
from ..zstd import ZstdTarFile
from .data import COMPRESSIONS, ZipData

__all__ = ["ZipStream"]


class ZipStream(RangeStream):
    def __init__(
        self,
        url: str,
        client=None,
        byte_range: Range | tuple[int, int] = Range("[0, 0)"),
        pruning_level: int = 0,
        scan_contents: bool = True,
    ):
        """
        As for RangeStream, but if `scan_contents` is True, then immediately call
        :meth:`check_central_dir_rec` on initialisation (which will perform a series
        of range requests to identify the files in the zip from the End of Central
        Directory Record and Central Directory Record), setting :attr:`zipped_files`,
        and :meth:`~RangeStream.add` their file content ranges to the stream.
        Setting this can be postponed until first access of the :attr:`filename_list`
        property (this will not :meth:`~RangeStream.add` them to the
        :class:`ZipStream`).

        Once parsed, the file contents are stored as a list of :class:`ZippedFileInfo`
        objects (in the order they appear in the Central Directory Record) in the
        :attr:`zipped_files` attribute.  Each of these objects has a
        :meth:`~ZippedFileInfo.file_range` method which gives the range of its file
        content bytes within the :class:`ZipStream`.
        """
        super().__init__(
            url=url, client=client, byte_range=byte_range, pruning_level=pruning_level
        )
        self.data = ZipData()
        if scan_contents:
            self.check_central_dir_rec()
            self.add_file_ranges()

    def check_head_bytes(self):
        start_sig = self.data.LOC_F_H.start_sig
        head_byte_range = Range(0, len(start_sig))
        self.add(head_byte_range)
        start_bytes = self.active_range_response.read()
        if start_bytes != start_sig:  # pragma: no cover
            # Actually think this will be if zip is empty
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
        if self.data.CTRL_DIR_REC.size is None:  # pragma: no cover
            self.check_end_of_central_dir_rec()
        size_cd_full = self.data.CTRL_DIR_REC.size  # total size of CDR (all entries)
        cd_read_offset = 0  # byte offset incremented after each entry
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
            zf_info = ZippedFileInfo.from_central_directory_entry(u)
            target = self.data.CTRL_DIR_REC.start_sig
            sig = zf_info.signature
            if sig != target:  # pragma: no cover
                raise ValueError(f"Bad Central Directory signature at {cd_start}")
            fn_len = zf_info.filename_length
            fn_rng = Range(cd_end, cd_end + fn_len)
            self.add(fn_rng)
            filename = self.active_range_response.read()
            flags = zf_info.flags
            if flags & 0x800:  # pragma: no cover
                # UTF-8 file names extension
                filename = filename.decode("utf-8")
            else:
                # Historical ZIP filename encoding
                filename = filename.decode("cp437")
            extra_len = zf_info.extra_field_length
            comment_len = zf_info.comment_length
            cd_read_offset += cd_size + fn_len + extra_len + comment_len
            zf_info = ZippedFileInfo.from_central_directory_entry(u, filename=filename)
            self.zipped_files.append(zf_info)
        return

    def add_file_ranges(self):
        for zf_info in self.zipped_files:
            self.add(zf_info.file_range, name=zf_info.filename)

    def get_central_dir_bytes(self, step=20):
        """
        Using the stored start position of the End Of Central Directory Record
        (or calculating and storing it if it is not yet set on the object),
        identify the files in the central directory record by searching backwards
        from the start of the End of Central Directory Record signature until
        finding the start of the Central Directory Record.
        """
        if self.data.E_O_CTRL_DIR_REC.start_pos is None:  # pragma: no cover
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
        else:  # pragma: no cover
            raise ValueError(f"No central directory start signature found")
        # cent_dir_rng.end = self.data.E_O_CTRL_DIR_REC.start_pos
        cd_byte_store = cd_byte_store[offset:]
        return cd_byte_store

    @property
    def filename_list(self) -> list[str]:
        """
        Return only the file name list from the stored list of 2-tuples
        of (filename, extra bytes).
        """
        if not hasattr(self, "zipped_files"):  # pragma: no cover
            self.check_central_dir_rec()
        return [f.filename for f in self.zipped_files]

    def decompress_zipped_file(
        self,
        zf_info: ZippedFileInfo,
        method: str | None = None,
        ext: str | None = None,
    ):
        """
        Given a :class:`ZippedFileInfo` object ``zf_info``, and (optionally)
        its compression method [or else detecting that], decompress its bytes
        from the stream.

        Args:
          zf_info : The compressed bytes
          method  : Compression method (2-3 character abbreviated extension, lower case)
          ext     : File extension to treat the bytes in the ``zf_info`` range as having
                    (an option if ``zf_info`` is not being provided)
        """
        zf_range = zf_info.file_range
        if method is None:
            if ext:
                try:  # pragma: no cover
                    method = next(
                        (_ext, m)
                        for _ext, m in COMPRESSIONS.items()
                        if _ext == ext or ext.endswith(_ext)
                    )  # type: ignore
                except StopIteration:
                    raise ValueError(f"No compression method for extension {ext}")
                finally:
                    fn_tar = zf_info.filename is not None and ".tar" in zf_info.filename
                    is_tar = fn_tar or ext.startswith(".t")
                    archive = "tar" if is_tar else None
            else:
                if zf_info.filename is None:  # pragma: no cover
                    raise NotImplementedError(
                        "Cannot detect compression method from file extension"
                        " (no file name provided)"
                    )
                try:
                    ext, method = next(
                        (ext, m)
                        for ext, m in COMPRESSIONS.items()
                        if zf_info.filename.endswith(ext)
                    )
                except StopIteration:  # pragma: no cover
                    raise ValueError(f"Could not detect '{zf_info}' compression method")
                finally:
                    assert ext is not None  # because mypy can't follow my logic
                    is_tar = ext.startswith(".t") or ".tar" in zf_info.filename
                    archive = "tar" if is_tar else None  # pragma: no cover
        elif method not in COMPRESSIONS.values():  # pragma: no cover
            raise ValueError(f"{method} is not a valid option ({COMPRESSIONS=})")
        else:  # pragma: no cover
            archive = None  # Can't detect an archive without extension, ¯\_(ツ)_/¯
        assert method is not None  # because mypy can't follow my logic
        zf_rng = zf_info.file_range
        if zf_rng not in self.ranges:  # pragma: no cover
            self.add(zf_rng)
        else:
            self.set_active_range(zf_rng)
        zf_bytes = self.active_range_response.read()
        return decompress(zf_bytes, method=method, archive=archive)


def decompress(b: bytes, method: str, archive: str | None = None):
    """
    Decompress the given bytes under the given method.

    Args:
      b       : The compressed bytes
      method  : The compression method (2-3 character abbreviated extension, lower case)
      archive : The archive method to extract (either 'zip', 'tar', or None).
    """
    accepted_archive_types = [None, "zip", "tar"]
    accepted_compression_types = set(COMPRESSIONS.values())
    if archive not in accepted_archive_types:  # pragma: no cover
        raise TypeError(f"{archive=} is not one of {accepted_archive_types=}")
    if method == "gz":  # pragma: no cover
        raise NotImplementedError("No gzip support yet...")
    elif method == "xz":  # pragma: no cover
        raise NotImplementedError("No xz support yet...")
    elif method == "bz2":  # pragma: no cover
        raise NotImplementedError("No bz2 support yet...")
    elif method == "zst":
        if archive == "tar":
            d = ZstdTarFile(io.BytesIO(b))
        elif archive == "zip":  # pragma: no cover
            raise NotImplementedError("No zip + zst support yet...")
        else:  # pragma: no cover
            d = ZstdFile(io.BytesIO(b))
    else:  # pragma: no cover
        raise TypeError(
            f"Decompression not implemented for {method} (accepted_compression_types=)"
        )
    return d


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
    """
    A class describing a zipped file according to the struct
    defining its metadata. Only a subset of all the fields are
    supported here (those useful for identifying and extracting
    the file contents from a stream).
    """

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
        cd_entry: tuple,
        filename: str | None = None,
    ):
        """
        Instantiate directly from an unpacked central directory struct
        (describing the zipped file entry in a standardised entry order).
        """
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

    @property
    def file_range(self):
        sig_start = self.local_header_offset
        start = sig_start + ZipData().LOC_F_H.get_size() + self.filename_length
        end = start + self.compressed_size
        return Range(start, end)
