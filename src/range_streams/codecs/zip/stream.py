from __future__ import annotations

import struct

from ranges import Range

from ...range_stream import RangeStream
from .data import ZipDataMixIn

__all__ = ["ZipStream"]


class ZipStream(RangeStream, ZipDataMixIn):
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

    def check_head_bytes(self):
        start_sig = self.LOC_F_H.start_sig
        head_byte_range = Range(0, len(start_sig))
        self.add(head_byte_range)
        start_bytes = self.active_range_response.read()
        if start_bytes != start_sig:
            # Actually think this will be if zip is empty? Test...
            raise ValueError(
                f"Invalid zip header sequence {start_bytes=!r}: expected {start_sig!r}"
            )

    def annotate_end_of_central_dir(self, step=20, limit=400):
        """
        Identify and store the start position of the End Of Central Directory Record
        by searching backwards from the end of the file stream for the EoCDR signature.
        """
        target = self.E_O_CTRL_DIR_REC.start_sig
        tail_rng = self.total_range
        tail_rng.start = tail_rng.end - step
        byte_cache = b""
        # tail_byte_store = b""
        cache_miss_size = len(target) - 1
        while tail_rng.start > 0 and self.total_range.end - tail_rng.start < limit:
            # print(f"Adding {tail_rng}")
            self.add(tail_rng)
            tail_bytes = self.active_range_response.read()
            # tail_byte_store = tail_bytes + tail_byte_store
            byte_cache = tail_bytes + byte_cache[:cache_miss_size]
            if target in byte_cache:
                offset = byte_cache.find(target)
                self.E_O_CTRL_DIR_REC.start_pos = tail_rng.start + offset
                break
            else:
                tail_rng.start -= step
                tail_rng.end -= step
        else:
            raise ValueError(f"Invalid zip end of central directory sequence")

    def get_central_dir_bytes(self, step=20):
        """
        Using the stored start position of the End Of Central Directory Record
        (or calculating and storing it if it is not yet set on the object),
        identify the files in the central directory record by searching backwards
        from the start of the End of Central Directory Record signature until
        finding the start of the Central Directory Record.
        """
        if self.E_O_CTRL_DIR_REC.start_pos is None:
            self.annotate_end_of_central_dir(step=step)
        pre_eocd = self.E_O_CTRL_DIR_REC.start_pos
        cent_dir_rng = Range(pre_eocd - step, pre_eocd)
        self.add(cent_dir_rng)
        target = self.CTRL_DIR_REC.start_sig
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
                self.CTRL_DIR_REC.start_pos = cent_dir_rng.start + offset
                break
            else:
                cent_dir_rng.start -= step
                cent_dir_rng.end -= step
        else:
            raise ValueError(f"No central directory start signature found")
        # cent_dir_rng.end = self.E_O_CTRL_DIR_REC.start_pos
        cd_byte_store = cd_byte_store[offset:]
        return cd_byte_store

    def get_central_dir_files(self, step=20) -> list[tuple[bytes, bytes]]:
        """
        Parse the central directory bytes into a list of files.
        """
        cdr_bytes = self.get_central_dir_bytes(step=step)
        cdr_size = self.CTRL_DIR_REC.get_size()
        cdr_bytes, cdr_post_bytes = cdr_bytes[:cdr_size], cdr_bytes[cdr_size:]
        cdr_rec = struct.unpack(self.CTRL_DIR_REC.struct, cdr_bytes)
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


class ZipFileContentRecord:
    def __init__(self, bytes):
        ...
