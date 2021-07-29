from __future__ import annotations

import io
import struct

from ranges import Range

from ...range_stream import RangeStream
from .data import COMPRESSIONS, TarData

__all__ = ["ZipStream"]


class TarStream(RangeStream):
    def __init__(
        self,
        url: str,
        client=None,
        byte_range: Range | tuple[int, int] = Range("[0, 0)"),
        pruning_level: int = 0,
        scan_headers: bool = True,
    ):
        """
        As for RangeStream, but if `scan_headers` is True, then immediately call
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
        if scan_headers:
            self.check_header_recs()
            self.add_file_ranges()

    def check_header_recs(self):
        """
        Scan through all header records in the file, building a list of
        :class:`range_streams.codecs.tar.TarredFileInfo` objects describing the
        files described by the headers (but do not download those corresponding
        archived file ranges).

        For efficiency, only look at the particular fields of interest, not the
        entire header each time.
        """
        self.tarred_files: list[TarredFileInfo] = []
        scan_tell = 0
        assert self.total_bytes is not None
        while scan_tell < (self.total_bytes - self.data.HEADER._H_END_PAD_SIZE):
            try:
                file_name = self.read_file_name(start_pos_offset=scan_tell)
            except StopIteration:
                # Expected if a tarball has more than 2 end-of-file padding records
                break
            file_size = self.read_file_size(start_pos_offset=scan_tell)
            pad_size = self.data.HEADER._H_PAD_SIZE
            pad_remainder = file_size % pad_size
            file_padding = (pad_size - pad_remainder) if pad_remainder else 0
            file_end_offset = pad_size + file_size + file_padding
            tf_info = TarredFileInfo(
                size=file_size,
                padded_size=file_end_offset,
                filename_length=len(file_name),
                header_offset=scan_tell,
                filename=file_name,
            )
            self.tarred_files.append(tf_info)
            scan_tell += (
                file_end_offset  # increment to move the cursor to the next file
            )

    def read_file_name(self, start_pos_offset: int = 0) -> str:
        file_name_rng_start = start_pos_offset + self.data.HEADER._H_FILENAME_START
        file_name_rng_end = file_name_rng_start + self.data.HEADER._H_FILENAME_SIZE
        file_name_rng = Range(file_name_rng_start, file_name_rng_end)
        self.add(file_name_rng)
        file_name_b = self.active_range_response.read().rstrip(b"\x00")
        if file_name_b == b"":
            raise StopIteration("Expected file name, got padding bytes")
        return file_name_b.decode("ascii")

    def read_file_size(self, start_pos_offset: int = 0) -> int:
        file_size_rng_start = start_pos_offset + self.data.HEADER._H_FILE_SIZE_START
        file_size_rng_end = file_size_rng_start + self.data.HEADER._H_FILE_SIZE_SIZE
        file_size_rng = Range(file_size_rng_start, file_size_rng_end)
        self.add(file_size_rng)
        file_size_b = self.active_range_response.read()
        file_size = int(file_size_b, 8)  # convert octal number from bitstring
        return file_size

    def add_file_ranges(self):
        for tf_info in self.tarred_files:
            assert tf_info.filename is not None
            self.add(tf_info.file_range, name=tf_info.filename)

    @property
    def filename_list(self) -> list[str]:
        """
        Return the names of files stored in
        :attr:`~range_streams.codecs.tar.TarStream.tarred_files`.
        """
        if not hasattr(self, "tarred_files"):  # pragma: no cover
            self.check_header_recs()
        return [f.filename for f in self.tarred_files if f.filename is not None]


class HeaderInfo:
    """
    Not used, may be useful if extending the class. Note USTAR format variant.
    """

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
        size: int,  # ignoring header and trailing padding
        padded_size: bytes | int,  # including both header and trailing padding
        filename_length: bytes | int,
        header_offset: int,
        filename: str | None,
    ):
        self.size = size
        self.padded_size = padded_size
        self.filename_length = filename_length
        self.header_offset = header_offset
        self.filename = filename

    def __repr__(self):
        return (
            f"{self.__class__.__name__}"
            f" '{self.filename if self.filename is not None else ''}'"
            f" @ {self.header_offset!r}: {self.size!r}B"
        )

    @property
    def file_range(self):
        start = self.header_offset
        end = start + self.size
        return Range(start, end)
