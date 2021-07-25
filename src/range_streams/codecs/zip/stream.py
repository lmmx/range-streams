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
            print("Found")
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
        else:
            print(f"{self.data.E_O_CTRL_DIR_REC.start_pos=}")
        eocd_rng = self.total_range
        eocd_rng.start = self.data.E_O_CTRL_DIR_REC.start_pos
        self.add(eocd_rng)
        b = self.active_range_response.read()[: self.data.E_O_CTRL_DIR_REC.get_size()]
        u = struct.unpack(self.data.E_O_CTRL_DIR_REC.struct, b)
        print(u)
        _ECD_ENTRIES_TOTAL = 4
        _ECD_OFFSET = 6
        self.data.CTRL_DIR_REC.entry_count = u[_ECD_ENTRIES_TOTAL]
        self.data.CTRL_DIR_REC.start_pos = (
            self.data.E_O_CTRL_DIR_REC.start_pos - u[_ECD_OFFSET]
        )
        # _ECD_SIZE = 5
        # self.data.CTRL_DIR_REC.length = u[_ECD_SIZE]
        return

    def check_central_dir_offset(self):
        """
        identify the offset for the central directory record from the EOCDR.
        """
        ...

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
            # print(f"Adding {cent_dir_rng}")
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
        print(cd_byte_store)
        print(cent_dir_rng.start + offset)
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

    # def search_back_to_end_of_central_dir(self, step=20, limit=400):
    #    """
    #    DEPRECATED

    #    Identify and store the start position of the End Of Central Directory Record
    #    by searching backwards from the end of the file stream for the EoCDR signature.
    #    """
    #    target = self.data.E_O_CTRL_DIR_REC.start_sig
    #    tail_rng = self.total_range
    #    tail_rng.start = tail_rng.end - step
    #    byte_cache = b""
    #    # tail_byte_store = b""
    #    cache_miss_size = len(target) - 1
    #    while tail_rng.start > 0 and self.total_range.end - tail_rng.start < limit:
    #        # print(f"Adding {tail_rng}")
    #        self.add(tail_rng)
    #        tail_bytes = self.active_range_response.read()
    #        # tail_byte_store = tail_bytes + tail_byte_store
    #        byte_cache = tail_bytes + byte_cache[:cache_miss_size]
    #        if target in byte_cache:
    #            offset = byte_cache.find(target)
    #            self.data.E_O_CTRL_DIR_REC.start_pos = tail_rng.start + offset
    #            break
    #        else:
    #            tail_rng.start -= step
    #            tail_rng.end -= step
    #    else:
    #        raise ValueError(f"Invalid zip end of central directory sequence")


class ZipFileContentRecord:
    def __init__(self, bytes):
        ...
