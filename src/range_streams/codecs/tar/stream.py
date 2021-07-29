from __future__ import annotations

import io
import struct

from pyzstd import ZstdFile
from ranges import Range

from ...range_stream import RangeStream
from ..zstd import ZstdTarFile
from .data import COMPRESSIONS, TarData

__all__ = ["ZipStream"]


class TarStream(RangeStream):
    def __init__(
        self,
        url: str,
        client=None,
        byte_range: Range | tuple[int, int] = Range("[0, 0)"),
        pruning_level: int = 0,
        scan_header: bool = True,
    ):
        """
        As for RangeStream, but if `scan_header` is True, then immediately call
        :meth:`check_header_rec` on initialisation (which will perform the necessary
        of range request to identify the files in the tar from the header record),
        setting :attr:`tarred_files`, and :meth:`~RangeStream.add` their file content
        ranges to the stream.

        Setting this can be postponed until first access of the :attr:`filename_list`
        property (this will not :meth:`~RangeStream.add` them to the
        :class:`TarStream`).

        Once parsed, the file contents are stored as a list of :class:`TarredFileInfo`
        objects (in the order they appear in the header record) in the
        :attr:`tarred_files` attribute.  Each of these objects has a
        :meth:`~TarredFileInfo.file_range` method which gives the range of its file
        content bytes within the :class:`TarStream`.
        """
        super().__init__(
            url=url, client=client, byte_range=byte_range, pruning_level=pruning_level
        )
        self.data = TarData()
        if scan_header:
            self.check_header_rec()
            # self.add_file_ranges()

    def check_header_rec(self):
        head_byte_range = Range(0, 257)  # rest of first 512 bytes is padding
        self.add(head_byte_range)
        start_bytes = self.active_range_response.read()


class HeaderInfo:
    _H_FILENAME = 0
    _H_FILE_MODE = 1
    _H_OWNER_UID = 2
    _H_GROUP_UID = 3
    _H_FILE_SIZE = 4
    _H_MTIME = 5
    _H_CHECKSUM = 6
    _H_LINK_INDICATOR = 7
    _H_LINKED_NAME = 8


class TarredFileInfo(HeaderInfo):
    """
    A class describing a zipped file according to the struct
    defining its metadata. Only a subset of all the fields are
    supported here (those useful for identifying and extracting
    the file contents from a stream).
    """

    def __init__(
        self,
        # signature: bytes | int,
        # flags: bytes | int,
        # compress_type: bytes | int,
        # compressed_size: bytes | int,
        # uncompressed_size: bytes | int,
        # filename_length: bytes | int,
        # extra_field_length: bytes | int,
        # comment_length: bytes | int,
        # local_header_offset: bytes | int,
        # filename: str | None,
    ):
        pass
        # self.signature = signature
        # self.flags = flags
        # self.compress_type = compress_type
        # self.compressed_size = compressed_size
        # self.uncompressed_size = uncompressed_size
        # self.filename_length = filename_length
        # self.extra_field_length = extra_field_length
        # self.comment_length = comment_length
        # self.local_header_offset = local_header_offset
        # self.filename = filename

    def __repr__(self):
        return (
            f"{self.__class__.__name__}"
            # f" '{self.filename if self.filename is not None else ''}'"
            # f" @ {self.local_header_offset!r}: {self.compressed_size!r}B"
        )

    # @classmethod
    # def from_central_directory_entry(
    #    cls,
    #    cd_entry: tuple,
    #    filename: str | None = None,
    # ):
    #    """
    #    Instantiate directly from an unpacked central directory struct
    #    (describing the zipped file entry in a standardised entry order).
    #    """
    #    signature = cd_entry[cls._CD_SIGNATURE]
    #    flags = cd_entry[cls._CD_FLAG_BITS]
    #    compress_type = cd_entry[cls._CD_COMPRESS_TYPE]
    #    compressed_size = cd_entry[cls._CD_COMPRESSED_SIZE]
    #    uncompressed_size = cd_entry[cls._CD_UNCOMPRESSED_SIZE]
    #    filename_length = cd_entry[cls._CD_FILENAME_LENGTH]
    #    extra_field_length = cd_entry[cls._CD_EXTRA_FIELD_LENGTH]
    #    comment_length = cd_entry[cls._CD_COMMENT_LENGTH]
    #    local_header_offset = cd_entry[cls._CD_LOCAL_HEADER_OFFSET]
    #    return cls(
    #        signature=signature,
    #        flags=flags,
    #        compress_type=compress_type,
    #        compressed_size=compressed_size,
    #        uncompressed_size=uncompressed_size,
    #        filename_length=filename_length,
    #        extra_field_length=extra_field_length,
    #        comment_length=comment_length,
    #        local_header_offset=local_header_offset,
    #        filename=filename,
    #    )

    # @property
    # def file_range(self):
    #    sig_start = self.local_header_offset
    #    start = sig_start + ZipData().LOC_F_H.get_size() + self.filename_length
    #    end = start + self.compressed_size
    #    return Range(start, end)
