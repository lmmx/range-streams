from __future__ import annotations

from io import SEEK_END, SEEK_SET, BytesIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    # absolute imports for Sphinx
    import range_streams  # for RangeStream, RangeRequest

from ranges import Range

from .range_utils import range_len

__all__ = ["RangeResponse"]


DEBUG_VERBOSE = False
ALWAYS_SET_TOLD = True  # if False, only windowed range responses set `.told`


class RangeResponse:
    """
    Adapted from `obskyr's ResponseStream demo code
    <https://gist.github.com/obskyr/b9d4b4223e7eaf4eedcd9defabb34f13>`_,
    this class handles the streamed partial request as a file-like object.
    """

    tail_mark: int = 0
    """
    The amount by which to shorten the 'tail' (i.e. the upper end) of the
    range when deciding if it is 'consumed'. Incremented within the
    :meth:`~range_streams.stream.RangeStream.handle_overlap` method
    when the ``pruning_level`` is set to ``1`` (indicating a "replant" policy).

    Under a 'replant' policy, when a new range is to be added and would overlap
    at the tail of an existing range, the pre-existing range should be effectively
    truncated by 'marking their tails'
    (where `an existing range` is assumed here to only be considered a range
    if it is not 'consumed' yet).
    """
    _bytes: BytesIO

    def __init__(
        self,
        stream: range_streams.RangeStream,
        range_request: range_streams.RangeRequest,
        range_name: str = "",
    ):
        self.parent_stream = stream
        self.request = range_request
        self.is_windowed = self.check_is_windowed()
        self.read_ready = not self.is_windowed
        if self.is_windowed or ALWAYS_SET_TOLD:
            self.told = 0
        if self.is_windowed:
            # Don't create a buffer, refer to the source range's RangeResponse buffer
            self._bytes = self.source_range_response._bytes
        else:
            self._bytes = BytesIO()
        self.range_name = range_name

    def __repr__(self):
        rng_name = self.range_name if self.range_name == "" else f' "{self.range_name}"'
        return (
            f"{self.__class__.__name__} ⠶{rng_name} {self.request.range} @ "
            f"'{self.parent_stream.name}' from {self.parent_stream.domain}"
        )

    @property
    def source_range_response(self) -> RangeResponse:
        """
        The RangeResponse associated with the source range, for a windowed range.
        Only access this if windowed (if not a windowed range, this will give the
        RangeResponse associated with the range at position 0, as the default
        :attr:`~range_streams.request.RangeRequest.window_on_range` value for
        non-windowed ranges is the empty range ``[0,0)``, whose start will be used as
        the key for the :attr:`~range_streams.stream.RangeStream._ranges` RangeDict).
        """
        if not self.is_windowed:
            raise ValueError("source_range_response accessed for non-windowed range")
        return self.parent_stream._ranges[self.source_range.start]

    @property
    def source_iterator(self):
        """
        The iterator associated with the source range, for a windowed range.
        """
        return self.source_range_response.request._iterator

    @property
    def _iterator(self):
        return self.source_iterator if self.is_windowed else self.request._iterator

    def check_is_windowed(self) -> bool:
        """
        Whether the associated request is windowed.
        Used to set :attr:`~range_streams.response.RangeResponse.is_windowed` on init
        """
        return not self.source_range.isempty()

    @property
    def source_range(self) -> Range:
        """
        Wrapper for :attr:`~range_streams.request.RangeRequest.window_on_range`
        with a less confusing name to access. Note that this will be the empty range
        if the request is not a windowed request.
        """
        return self.request.window_on_range

    @property
    def is_in_window(self) -> bool:
        """
        Whether file cursor is in the window. Trivially true for a non-windowed request,
        otherwise checks if the file cursor is currently within (or exactly at the end
        of) the window range.
        """
        if self.is_windowed:
            return self._bytes.tell() in Range(
                self.request.range.start,
                self.request.range.end,
                include_start=True,
                include_end=True,
            )
        else:
            return True

    def tell_abs(self, live=True) -> int:
        """
        Get the absolute file cursor position from either the active range response tell
        (if ``live`` is ``True``: default) or the position stored on the active range
        response (if ``live`` is ``False``).

        Both are given as ``absolute`` positions by adding the
        :attr:`~range_streams.response.RangeResponse.window_offset`, (which is 0 for
        non-windowed ranges).
        """
        return (self.told if live else self.tell()) + self.window_offset

    def store_tell(self) -> None:
        """
        Store the [window-relative] tell value in
        :attr:`~range_streams.response.RangeResponse.told`
        in the event of any read, seek, or load on the stream, when accessed through the
        RangeResponse (do not access directly if you want to keep a reliable stored
        value for :attr:`~range_streams.response.RangeResponse.told`).
        """
        if self.is_windowed or ALWAYS_SET_TOLD:
            self.told = self.tell()

    @property
    def window_offset(self) -> int:
        has_offset = self.is_windowed and self.request.range > self.source_range
        return self.request.range.start - self.source_range.start if has_offset else 0

    def prepare_reading_window(self):
        """
        Prepare the stream cursor for reading (unclear if this should only be done on
        initialisation...) Should be done every time if the cursor is shared, but is it?
        """
        if not self.is_in_window:
            self.seek(position=0)  # Window offset is added in seek function
        self.read_ready = True  # Remove barrier flag attribute
        if DEBUG_VERBOSE:
            print("\n---READ_READY removed\n---")

    @property
    def client(self):
        return self.request.client

    @property
    def url(self) -> str:
        """
        A wrapper to access the :attr:`~range_streams.stream.RangeStream.url`
        of the 'parent' :class:`~range_streams.stream.RangeStream`.
        """
        return self.parent_stream.url

    @property
    def name(self) -> str:
        """
        A wrapper to access the :attr:`~range_streams.stream.RangeStream.name`
        of the 'parent' :class:`~range_streams.stream.RangeStream`.
        """
        return self.parent_stream.name

    def _load_all(self) -> None:
        """
        If seeking on a windowed range, then 'loading all' will not really
        load to the end of the stream, just the end of the window onto it.
        """
        if self.is_windowed:
            # Would need to offset this if source range is non-total range
            window_end = self.request.range.end
            self._load_until(window_end)
        else:
            self._bytes.seek(0, SEEK_END)
            for chunk in self._iterator:
                self._bytes.write(chunk)
        self.store_tell()

    def _load_until(self, goal_position):
        current_position = self._bytes.seek(0, SEEK_END)
        while current_position < goal_position:
            try:
                current_position += self._bytes.write(next(self._iterator))
            except StopIteration:
                break
        self.store_tell()

    def tell(self) -> int:
        """
        File-like tell (position indicator) within the range request stream.
        """
        if not self.read_ready:
            # If it's not yet ready, lie about where the cursor is (give where it will be)
            t = 0
            if DEBUG_VERBOSE:
                print("Blanked the tell: not ready")
        elif self.is_windowed:
            t = self._bytes.tell() - self.window_offset
            if DEBUG_VERBOSE:
                print(f"{t=} (windowed tell)")
        else:
            t = self._bytes.tell()
            if DEBUG_VERBOSE:
                print(f"{t=} (plain tell)")
        return t

    def read(self, size=None):
        """
        File-like reading within the range request stream.
        """
        if not self.read_ready:
            # Only run on the first use after init
            self.prepare_reading_window()
        left_off_at = self._bytes.tell()
        if size is None:
            self._load_all()
        else:
            goal_position = left_off_at + size
            if DEBUG_VERBOSE:
                print(f"{goal_position=} = {left_off_at=} + {size=}")
            # Probably overshoots the cursor (loads a chunk at a time)
            self._load_until(goal_position)

        # Rewind the cursor to the start position now the bytes to read are loaded
        self._bytes.seek(left_off_at)
        read_bytes = self._bytes.read(size)
        self.store_tell()
        return read_bytes

    def seek(self, position, whence=SEEK_SET):
        """
        File-like seeking within the range request stream.
        """
        if whence == SEEK_END:
            self._load_all()
        if self.is_windowed:
            position = position + self.window_offset
        self._bytes.seek(position, whence)
        self.store_tell()

    @property
    def total_len_to_read(self):
        return range_len(self.request.range) + 1

    def is_consumed(self) -> bool:
        """
        Whether the :meth:`~range_streams.response.RangeResponse.tell`
        position (indicating 'consumed' or 'read so far') along with the
        :attr:`~range_streams.response.RangeResponse.tail_mark` indicates
        whether the stream should be considered consumed.

        The :attr:`~range_streams.response.RangeResponse.tail_mark`
        is part of a mechanism to 'shorten' ranges when an overlap is detected,
        to preserve the one-to-one integrity of the :class:`~ranges.RangeDict`
        (see notes on the "replant" policy of
        :meth:`~range_streams.stream.RangeStream.handle_overlap`, set
        by the ``pruning_level`` passed into
        :class:`~range_streams.stream.RangeStream` on initialisation).

        Note that there is (absolutely!) nothing stopping a stream from being
        re-consumed, but this library works on the assumption that all streams
        will be handled in an efficient manner (with any data read out from them
        either used once only or else will be reused from the first output rather
        than re-accessed directly from the stream itself).

        To this end, :class:`~range_streams.stream.RangeStream` has measures
        in place to "decommission" ranges once they are consumed (see in particular
        :meth:`~range_streams.stream.RangeStream.burn_range` and
        :meth:`~range_streams.stream.RangeStream.handle_overlap`).
        """
        tail_mark = self.tail_mark
        if not self.is_in_window:
            # File cursor position may not be set to the start of the window but when it
            # is read it will be placed at the start (don't do this here: checking if
            # consumed shouldn't move the cursor) The window start position will become
            # the ``tell()`` upon first ``read()``
            read_so_far = 0
        else:
            read_so_far = self.tell()
        len_to_read = self.total_len_to_read - tail_mark
        return (len_to_read - read_so_far) <= 0  # should not go below!
