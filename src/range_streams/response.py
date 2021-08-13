from __future__ import annotations

from io import SEEK_END, SEEK_SET, BytesIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    # absolute imports for Sphinx
    import range_streams  # for RangeStream, RangeRequest

from ranges import Range

from .range_utils import ALWAYS_SET_TOLD, range_len

__all__ = ["RangeResponse"]


DEBUG_VERBOSE = False


class BufferLedger(BytesIO):
    """
    A thin wrapper to :class:`io.BytesIO` with an attribute
    """

    def __init__(self, active_rng: Range = Range(0, 0)):
        super().__init__()
        self.active_buf_range: Range = active_rng


class RangeResponse:
    """
    Adapted from `obskyr's ResponseStream demo code
    <https://gist.github.com/obskyr/b9d4b4223e7eaf4eedcd9defabb34f13>`_,
    this class handles the streamed partial request as a file-like object.

    Don't forget to close the ``httpx.Response`` yourself! The
    :meth:`~range_streams.response.RangeResponse.close` method is available
    (or :meth:`~range_streams.stream.RangeStream.close`) to help you.
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
    _bytes: BufferLedger

    def __init__(
        self,
        stream: range_streams.RangeStream,
        range_request: range_streams.RangeRequest,
        range_name: str = "",
    ):
        self.parent_stream = stream
        self.request = range_request
        self.range_name = range_name
        self.is_windowed = self.check_is_windowed()
        self.read_ready = not self.is_windowed
        if self.is_windowed or ALWAYS_SET_TOLD:
            self.told = 0
        if self.is_windowed:
            # Don't create a buffer, refer to the source range's RangeResponse buffer
            self._bytes = self.source_range_response._bytes
        else:
            self._bytes = BufferLedger()

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

    def set_active_buf_range(self, rng: Range) -> None:
        """
        Update the :attr:`~range_streams.response.RangeResponse._bytes` buffer's
        :attr:`~range_streams.response.RangeResponse._bytes.active_buf_range`
        attribute with the given :~ranges.Range` (``rng``).
        """
        self._bytes.active_buf_range = rng

    @property
    def is_active_buf_range(self) -> bool:
        """
        The active range is stored on the buffer the HTTP response stream writes to
        (in the :attr:`~range_streams.response.RangeResponse._bytes.active_buf_range`
        attribute) so that whenever the active range changes, it is detectable
        immediately (all interfaces to read/seek/load the buffer are 'guarded' by a
        call to :meth:`~range_streams.response.RangeResponse.buf_keep` to achieve this).

        When this change is detected, since the cursor may be in another range of the
        shared source buffer (where the previously active window was busy doing its
        thing), the cursor is first moved to the last stored
        :meth:`~range_streams.response.RangeResponse.tell` position, which is stored on
        each :class:`~range_streams.response.RangeResponse` in the
        :attr:`~range_streams.response.RangeResponse.told` attribute, and initialised as
        ``0`` so that on first use it simply refers to the start position of the window
        range.

        Note that the active range only changes for 'windowed'
        :class:`~range_streams.response.RangeResponse` objects sharing a 'source' buffer
        with a source :class:`~range_streams.response.RangeResponse in the
        :attr:`~range_streams.stream.RangeStream._ranges` :class:`~ranges.RangeDict`.
        To clarify: the active range changes on first use for non-windowed ranges, since
        the active range is initialised as the empty range (but after that it doesn't!)
        """
        return self._bytes.active_buf_range == self.request.range

    def verify_sync(self, msg=""):
        if self.parent_stream.client_is_async:
            raise ValueError(f"Synchronous client check failed{msg}")

    def verify_async(self, msg=""):
        if not self.parent_stream.client_is_async:
            raise ValueError(f"Asynchronous client check failed{msg}")

    @property
    def source_iterator(self):
        """
        The iterator associated with the source range, for a windowed range.
        """
        self.verify_sync(msg=" when accessing source_iterator property")
        return self.source_range_response.request._iterator

    @property
    def _iterator(self):
        self.verify_sync(msg=" when accessing iterator property")
        return self.source_iterator if self.is_windowed else self.request._iterator

    @property
    def source_aiterator(self):
        """
        The async iterator associated with the source range, for a windowed range.
        """
        self.verify_async(msg=" when accessing source_aiterator property")
        return self.source_range_response.request._aiterator

    @property
    def _aiterator(self):
        self.verify_async(msg=" when accessing aiterator property")
        return self.source_aiterator if self.is_windowed else self.request._aiterator

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

    def buf_keep(self) -> None:
        """
        If the currently set active buffer range on the
        :attr:`~range_streams.response.RangeResponse._bytes` buffer
        is not the range on this
        :class:`~range_streams.response.RangeResponse`, then set it to be.

        This is the mechanism by which windowed ranges are switched (the windows
        share the same 'source' buffer, and the value of the active buffer range
        stored on that buffer indicates the most recently active window).

        At initialisation, all :class:`~range_streams.response.RangeResponse`
        have their active buffer range set to the empty range, ``Range(0,0)``.
        """
        if not self.is_active_buf_range:
            rng = self.request.range
            if DEBUG_VERBOSE:
                print(f"Buffer switch... {rng=}")
            if self.is_windowed:
                cursor_dest = rng.start + self.told
                if DEBUG_VERBOSE:
                    print(f"... {self.told=}")
                self._bytes.seek(cursor_dest)
            # Do not set `told` as it was just used (i.e. redundant to do so)
            self.set_active_buf_range(rng=rng)

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

    def prepare_reading_window(self) -> None:
        """
        Prepare the stream cursor for reading (unclear if this should only be done on
        initialisation...) Should be done every time if the cursor is shared, but is it?
        """
        # UPDATE: MAY BE REDUNDANT AFTER `buf_keep` IMPLEMENTED? TODO: TEST
        if not self.is_in_window:
            self.seek(position=0)  # Window offset is added in seek function
        self.read_ready = True  # Remove barrier flag attribute
        if DEBUG_VERBOSE:
            print("\n---READ_READY removed\n---")

    @property
    def client(self):  # Returns: httpx.Client | httpx.AsyncClient
        """
        The request's client.
        """
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
        self.verify_sync(msg=" when loading all")
        self.buf_keep()
        if self.is_windowed:
            # Would need to offset this if source range is non-total range
            # (also may need to take into account tail-mark for windows?)
            window_end = self.request.range.end
            self._load_until(window_end)
        else:
            self._bytes.seek(0, SEEK_END)
            for chunk in self._iterator:
                self._bytes.write(chunk)
        self.store_tell()

    async def _aload_all(self) -> None:
        """
        If seeking on a windowed range, then 'loading all' will not really
        load to the end of the stream, just the end of the window onto it.
        """
        self.verify_async(msg=" when loading all")
        self.buf_keep()
        if self.is_windowed:
            # Would need to offset this if source range is non-total range
            # (also may need to take into account tail-mark for windows?)
            window_end = self.request.range.end
            await self._aload_until(window_end)
        else:
            self._bytes.seek(0, SEEK_END)
            async for chunk in self._aiterator:
                self._bytes.write(chunk)
        self.store_tell()

    def _load_until(self, goal_position: int) -> None:
        self.verify_sync(msg=f" when loading until {goal_position}")
        self.buf_keep()
        current_position = self._bytes.seek(0, SEEK_END)
        while current_position < goal_position:
            try:
                current_position += self._bytes.write(next(self._iterator))
            except StopIteration:
                break
        self.store_tell()

    async def _aload_until(self, goal_position: int) -> None:
        self.verify_async(msg=f" when loading until {goal_position}")
        self.buf_keep()
        current_position = self._bytes.seek(0, SEEK_END)
        while current_position < goal_position:
            try:
                awaited_bytes = await self._aiterator.__anext__()
                current_position += self._bytes.write(awaited_bytes)
            except StopAsyncIteration:
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

    def _prepare_to_read(self) -> int:
        """
        Called at the start of :meth:`~range_streams.response.RangeResponse.read` to
        ensure the reading window is prepared (on the first read of a windowed range)
        and acquire the starting position.
        """
        self.buf_keep()
        if DEBUG_VERBOSE:
            print(f"Reading {self.request.range}")
        if not self.read_ready:
            # Only run on the first use after init
            self.prepare_reading_window()
        return self._bytes.tell()

    def read(self, size: int | None = None) -> bytes:
        """
        File-like reading within the range request stream, with careful handling of
        windowed ranges and tail marks.
        """
        self.verify_sync(msg=f" when reading {size} bytes")
        left_off_at = self._prepare_to_read()
        if size is None:
            self._load_all()
        else:
            goal_position = left_off_at + size
            if DEBUG_VERBOSE:
                print(f"{goal_position=} = {left_off_at=} + {size=}")
            # Probably overshoots the cursor (loads a chunk at a time)
            self._load_until(goal_position)

        read_bytes = self._get_read_bytes(size=size, left_off_at=left_off_at)
        return read_bytes

    async def aread(self, size: int | None = None) -> bytes:
        """
        File-like reading within the range request stream, with careful handling of
        windowed ranges and tail marks.
        """
        self.verify_async(msg=f" when reading {size} bytes")
        left_off_at = self._prepare_to_read()
        if size is None:
            await self._aload_all()
        else:
            goal_position = left_off_at + size
            if DEBUG_VERBOSE:
                print(f"{goal_position=} = {left_off_at=} + {size=}")
            # Probably overshoots the cursor (loads a chunk at a time)
            await self._aload_until(goal_position)
        read_bytes = self._get_read_bytes(size=size, left_off_at=left_off_at)
        return read_bytes

    def _get_read_bytes(self, size: int | None, left_off_at: int) -> bytes:
        """
        Called at the end of :meth:`~range_streams.response.RangeResponse.read` and
        :meth:`~range_streams.response.RangeResponse.aread` to rewind the cursor to the
        starting position after the bytes to read are loaded [from the a/sync iterator],
        read said bytes and return them (ensuring to store the final cursor position).
        """
        self._bytes.seek(left_off_at)
        if self.is_windowed:
            # Convert absolute window end to relative offset on source range
            # (should do this using window_offset to permit non-total ranges!)
            window_end = self.request.range.end - self.tail_mark
            remaining_bytes = window_end - left_off_at
        else:
            rng_len = self.total_len_to_read
            remaining_bytes = rng_len - left_off_at
        if size is None or size > remaining_bytes:
            size = remaining_bytes
        read_bytes = self._bytes.read(size)
        self.store_tell()
        return read_bytes

    def seek(self, position: int, whence=SEEK_SET):
        """
        File-like seeking within the range request stream. Synchronous only.
        """
        msg = "No negative seek so `RangeResponse.seek` is synchronous (try `load_all`)"
        self.buf_keep()
        if whence == SEEK_END:
            if self.request.client_is_async:
                raise NotImplementedError(msg)
            else:
                self._load_all()
        if self.is_windowed:
            position = position + self.window_offset
        self._bytes.seek(position, whence)
        self.store_tell()

    @property
    def total_len_to_read(self):
        return range_len(self.request.range) + 1 - self.tail_mark

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
        if not self.is_in_window:
            # File cursor position may not be set to the start of the window but when it
            # is read it will be placed at the start (don't do this here: checking if
            # consumed shouldn't move the cursor) The window start position will become
            # the ``tell()`` upon first ``read()``
            read_so_far = 0
        else:
            read_so_far = self.tell()
        len_to_read = self.total_len_to_read
        return (len_to_read - read_so_far) <= 0  # should not go below!

    @property
    def is_closed(self):
        """
        True if the associated ``httpx.Response`` object is closed. For a windowed
        response in single request mode, this will be shared with any/all other windowed
        responses on the stream.
        """
        return self.request.response.is_closed

    def close(self):
        """
        Close the associated ``httpx.Response`` object. In single request mode, there is
        just the one (shared with all the 'windowed' responses).
        """
        self.verify_sync(msg=f" when closing the request response on {self}")
        self.request.response.close()

    async def aclose(self):
        """
        Close the associated ``httpx.Response`` object. In single request mode, there is
        just the one (shared with all the 'windowed' responses).
        """
        self.verify_async(msg=f" when closing the request response on {self}")
        await self.request.response.aclose()
