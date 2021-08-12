from __future__ import annotations

import io
import struct

from ranges import Range

from ...stream import RangeStream
from .data import COMPRESSIONS, TarData

__all__ = ["TarStream", "TarredFileInfo"]


class TarStream(RangeStream):
    """
    As for :class:`~range_streams.stream.RangeStream`, but if ``scan_headers``
    is ``True``, then immediately call
    :meth:`~range_streams.codecs.tar.TarStream.check_header_recs`
    on initialisation (which will perform the necessary
    of range request to identify the files in the tar from the header record),
    setting :attr:`~range_streams.codecs.tar.TarStream.tarred_files`, and
    :meth:`~range_streams.stream.RangeStream.add` their file content ranges to the stream.

    Setting this can be postponed until first access of the :attr:`filename_list`
    property (this will not :meth:`~range_streams.stream.RangeStream.add` them to the
    :class:`~range_streams.codecs.tar.TarStream`).

    Once parsed, the file contents are stored as a list of
    :class:`~range_streams.codecs.tar.stream.TarredFileInfo`
    objects (in the order they appear in the header record) in the
    :attr:`tarred_files` attribute.  Each of these objects has a
    :meth:`~range_streams.codecs.tar.stream.TarredFileInfo.file_range`
    method which gives the range of its file content bytes within the
    :class:`~range_streams.codecs.tar.TarStream`.
    """

    def __init__(
        self,
        url: str,
        client=None,
        byte_range: Range | tuple[int, int] = Range("[0, 0)"),
        pruning_level: int = 0,
        scan_headers: bool = True,
        single_request: bool = False,
        force_async: bool = False,
        chunk_size: int | None = None,
    ):
        """
        Set up a stream for the ZIP archive at ``url``, with either an initial
        range to be requested (HTTP partial content request), or if left
        as the empty range (default: ``Range(0,0)``) a HEAD request will
        be sent instead, so as to set the total size of the target
        file on the :attr:`~range_streams.stream.RangeStream.total_bytes`
        property.

        By default (if ``client`` is left as ``None``) a fresh
        :class:`httpx.Client` will be created for each stream.

        The ``byte_range`` can be specified as either a :class:`~ranges.Range`
        object, or 2-tuple of integers (``(start, end)``), interpreted
        either way as a half-closed interval ``[start, end)``, as given by
        Python's built-in :class:`range`.

        The ``pruning_level`` controls the policy for overlap handling
        (``0`` will resize overlapped ranges, ``1`` will delete overlapped
        ranges, and ``2`` will raise an error when a new range is added
        which overlaps a pre-existing range).

        If ``single_request`` is ``True`` (default: ``False``), then the behaviour when
        an empty ``byte_range`` is passed instead becomes to send a standard streaming
        GET request (not a partial content request at all), and instead the class will
        then facilitate an interface that 'simulates' these calls, i.e. as if each time
        :meth:`~range_streams.stream.RangeStream.add` was used the range requests were
        being returned instantly (as everything needed was already obtained on the first
        request at initialisation). More performant when reading a stream linearly.

        - See docs for the
          :meth:`~range_streams.stream.RangeStream.handle_overlap`
          method for further details.

        Args:
          url            : (:class:`str`) The URL of the file to be streamed
          client         : (:class:`httpx.Client` | ``None``) The HTTPX client
                           to use for HTTP requests
          byte_range     : (:class:`~ranges.Range` | ``tuple[int,int]``) The range
                           of positions on the file to be requested
          pruning_level  : (:class:`int`) Either ``0`` ('replant'), ``1`` ('burn'),
                           or ``2`` ('strict')
          scan_headers   : (:class:`bool`) Whether to scan the archive headers
                           upon initialisation and add the archive's file ranges
          single_request : (:class:`bool`) Whether to use a single GET request and
                           just add 'windows' onto this rather than create multiple
                           partial content requests.
          force_async    : (:class:`bool` | ``None``) Whether to require the client
                           to be ``httpx.AsyncClient``, and if no client is given,
                           to create one on initialisation. (Experimental/WIP)
          chunk_size     : (:class:`int` | ``None``) The chunk size used for the
                           ``httpx.Response.iter_raw`` response byte iterators
        """
        super().__init__(
            url=url,
            client=client,
            byte_range=byte_range,
            pruning_level=pruning_level,
            single_request=single_request,
        )
        self.data = TarData()
        if scan_headers:
            self.check_header_recs()
            self.add_file_ranges()

    def check_header_recs(self):
        """
        Scan through all header records in the file, building a list of
        :class:`~range_streams.codecs.tar.stream.TarredFileInfo` objects describing the
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
        """
        Return the file name by reading the file name for the header block starting at
        ``start_pos_offset`` (which for the first file will be ``0``, the default).
        Tar archives end with at least two empty blocks (i.e. 1024 bytes of padding),
        but there may be more than that. To catch this possibility, this method will
        raise a :class`StopIteration` error if the file name if NULL (i.e. if what was
        expected to be a file name is actually padding).
        """
        file_name_rng_start = start_pos_offset + self.data.HEADER._H_FILENAME_START
        file_name_rng_end = file_name_rng_start + self.data.HEADER._H_FILENAME_SIZE
        file_name_rng = Range(file_name_rng_start, file_name_rng_end)
        if self.client_is_async:
            self.add_async(file_name_rng)
        else:
            self.add(file_name_rng)
        file_name_b = self.active_range_response.read().rstrip(b"\x00")
        if file_name_b == b"":
            raise StopIteration("Expected file name, got padding bytes")
        return file_name_b.decode("ascii")

    def read_file_size(self, start_pos_offset: int = 0) -> int:
        """
        Parse the file size field of the archived file whose header record begins at
        ``start_pos_offset``.
        """
        file_size_rng_start = start_pos_offset + self.data.HEADER._H_FILE_SIZE_START
        file_size_rng_end = file_size_rng_start + self.data.HEADER._H_FILE_SIZE_SIZE
        file_size_rng = Range(file_size_rng_start, file_size_rng_end)
        if self.client_is_async:
            self.add_async(file_size_rng)
        else:
            self.add(file_size_rng)
        file_size_b = self.active_range_response.read()
        file_size = int(file_size_b, 8)  # convert octal number from bitstring
        return file_size

    def add_file_ranges(self):
        for tf_info in self.tarred_files:
            assert tf_info.filename is not None
            if self.client_is_async:
                self.add_async(tf_info.file_range, name=tf_info.filename)
            else:
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
