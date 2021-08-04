r""":mod:`range_streams.stream` exposes a class
:class:`~range_streams.stream.RangeStream`, whose key property (once initialised) is
:attr:`~range_streams.stream.RangeStream.ranges`,
which provides a :class:`~ranges.RangeDict` comprising the ranges of
the file being streamed.

The method :meth:`~range_streams.stream.RangeStream.add` will request further ranges,
and (unlike the other methods in this module) will accept a tuple of two integers as its
argument (``byte_range``).
"""

from __future__ import annotations

from copy import deepcopy
from io import SEEK_SET
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

MYPY = False  # when using mypy will be overrided as True
if MYPY or not TYPE_CHECKING:  # pragma: no cover
    import httpx  # avoid importing to Sphinx type checker

from ranges import Range, RangeDict

from .http_utils import detect_header_value, range_header
from .overlaps import get_range_containing, overlap_whence
from .range_utils import (
    ALWAYS_SET_TOLD,
    most_recent_range,
    range_max,
    range_span,
    range_termini,
    ranges_in_reg_order,
    validate_range,
)
from .request import RangeRequest
from .response import RangeResponse

__all__ = ["RangeStream"]

DEBUG_VERBOSE = False


class RangeStream:
    """
    A class representing a file being streamed from a server which supports
    range requests, with the `ranges` property providing a list of those
    intervals requested so far (and not yet exhausted).

    When the class is initialised its length checked upon the first range
    request, and the client provided is not closed (you must handle this
    yourself). Further ranges may be requested on the
    :class:`~range_streams.stream.RangeStream` by calling
    :meth:`~range_streams.stream.RangeStream.add`.

    Both the :meth:`~range_streams.stream.RangeStream.__init__` and
    :meth:`~range_streams.stream.RangeStream.add` methods support
    the specification of a range interval as either a tuple of two
    integers or a :class:`~ranges.Range` from the :mod:`python-ranges` package
    (an external requirement installed alongside this package). Either
    way, the interval created is interpreted to be the standard Python
    convention of a half-open interval ``[start,stop)``.
    """

    _length_checked: bool = False
    _active_range: Range | None = None
    """
    Set by :meth:`~range_streams.stream.RangeStream.set_active_range`,
    through which the
    :attr:`~range_streams.stream.RangeStream.active_range_response`
    property gives access to the currently 'active' range (usually
    the most recently created).
    """

    _ranges: RangeDict
    """
    `'Internal'` ranges attribute. Start position is not affected by
    reading in bytes from the :class:`RangeResponse` (unlike the
    'external' :attr:`~range_streams.stream.RangeStream.ranges` property)
    """

    def __init__(
        self,
        url: str,
        client=None,  # don't hint httpx.Client (Sphinx gives error)
        byte_range: Range | tuple[int, int] = Range("[0, 0)"),
        pruning_level: int = 0,
        single_request: bool = False,
        force_async: bool = False,
    ):
        """
        Set up a stream for the file at ``url``, with either an initial
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

        If ``byte_range`` is passed as the empty range ``Range(0,0)`` (its default),
        then a HEAD request is sent to ``url`` on initialisation, setting the
        :attr:`~range_streams.stream.RangeStream.total_bytes` value from the
        ``content-length`` header in the subsequent response.

        If ``single_request`` is ``True`` (default: ``False``), then the behaviour when
        an empty ``byte_range`` is passed instead becomes to send a standard streaming
        GET request (not a partial content request at all), and instead the class will
        then facilitate an interface that 'simulates' these calls, i.e. as if each time
        :meth:`~range_streams.stream.RangeStream.add` was used the range requests were
        being returned instantly (as everything needed was already obtained on the first
        request at initialisation). More performant when reading a stream linearly.

        Note: internally, this single request is known as 'the monostream', and is
        stored on the :attr:`~range_streams.stream.RangeStream.monostream` property.

        Note: a single request will not be as efficient if streaming the response
        non-linearly (since reading a byte in the stream requires loading all bytes up
        to it). This will mean it is only performant to use for certain file types or
        applications (e.g. a ZIP file is read "in a principled manner" from the end
        [the Central Directory] first, so gains greatly from using multiple partial
        content requests rather than a single stream, whereas a PNG file can only be
        read "in a principled manner" linearly, iterating through the chunks from the
        start).

        The ``pruning_level`` controls the policy for overlap handling
        (``0`` will resize overlapped ranges, ``1`` will delete overlapped
        ranges, and ``2`` will raise an error when a new range is added
        which overlaps a pre-existing range).

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
          single_request : (:class:`bool`) Whether to use a single GET request and
                           just add 'windows' onto this rather than create multiple
                           partial content requests.
          force_async    : (:class:`bool` | ``None``) Whether to require the client
                           to be ``httpx.AsyncClient``, and if no client is given,
                           to create one on initialisation. (Experimental/WIP)
        """
        self.url = url
        self.set_client(client=client, force_async=force_async)
        self.pruning_level = pruning_level
        self.single_request = single_request
        self._ranges = RangeDict()
        self._range_windows = RangeDict()
        self.add(byte_range=byte_range)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__} ⠶ {self.__ranges_repr__()} @@ "
            f"'{self.name}' from {self.domain}"
        )

    @property
    def freely_requestable(self):
        """
        Trivial opposite of the :attr:`~range_streams.stream.RangeStream.single_request`
        attribute, so that conditional blocks can treat this as the 'conventional' case
        and the single request case be the alternative (which looks better).
        """
        return not self.single_request

    def set_client(self, client, force_async: bool) -> None:
        """
        Check client type explicitly to handle a/sync and optional HTTPX client.

        Args:
          client      : (:class:`httpx.Client` | class:`httpx.AsyncClient` | ``None``)
                        The client to be used for all HTTP requests made on the
                        `range_streams.stream.RangeStream`. If ``None``, a fresh one
                        will be created.
          force_async : (:class:`bool`) If the ``client`` is ``None``, this parameter
                        determines whether :class:`httpx.Client` or
                        class:`httpx.AsyncClient` is set as the client. If a
                        synchronous client is given and ``force_async`` is ``True``,
                        an error will be raised.
        """
        if client is None:
            client = httpx.AsyncClient() if force_async else httpx.Client()
        elif isinstance(client, httpx.Client):
            if force_async:
                raise TypeError(f"{client=} is not async (`httpx.AsyncClient`)")
        elif not isinstance(client, httpx.AsyncClient):
            raise TypeError(f"{client=} is not a HTTPX client")
        self.client = client

    @property
    def client_is_async(self):
        return isinstance(self.client, httpx.AsyncClient)

    @property
    def sync_client(self):  # returns httpx.Client | httpx.AsyncClient | None
        """
        Provide a synchronous client: either the stream's client, or a fresh one
        if the stream's client is asynchronous. Used for HEAD requests on an async
        RangeStream. Presumes a client has been set correctly.
        """
        return httpx.Client() if self.client_is_async else self.client

    def __ranges_repr__(self) -> str:
        return ", ".join(map(str, self.list_ranges()))

    def check_is_subrange(self, rng: Range):
        if rng not in self.total_range:
            raise ValueError(f"{rng} is not a sub-range of {self.total_range}")

    def check_range_integrity(self, use_windows=False) -> None:
        """
        Every :class:`~ranges.RangeSet` in the
        :attr:`~range_streams.stream.RangeStream._ranges`
        :class:`~ranges.RangeDict` keys must contain 1 :class:`~ranges.Range` each
        """
        rng_dict = self._range_windows if use_windows else self._ranges
        if sum(len(rs._ranges) - 1 for rs in rng_dict.ranges()) != 0:
            bad_rs = [rs for rs in rng_dict.ranges() if len(rs._ranges) - 1 != 0]
            for rset in bad_rs:
                for rng in rset:
                    rng_resp = rng_dict[rng.start]
                    rng_max = range_max(rng)
                    if rng_resp.tell() > rng_max:
                        rset.discard(rng)  # discard subrange
                if len(rset.ranges()) < 2:
                    bad_rs.remove(rset)
            if bad_rs:
                raise ValueError(f"Each RangeSet must contain 1 Range: found {bad_rs=}")

    def compute_external_ranges(self, use_windows: bool = False) -> RangeDict:
        """
        If ``use_windows`` is ``True``, the ``internal_range_dict``
        is :attr:`~range_streams.stream.RangeStream._range_windows`
        rather than :attr:`~range_streams.stream.RangeStream._ranges`
        when ``use_windows`` is ``False`` (default: ``False``).

        Modifying the ``internal_range_dict`` attribute to account for the bytes
        consumed (from the head) and tail mark offset of where a range was already
        trimmed to avoid an overlap (from the tail).

        While the :class:`~ranges.RangeSet` keys are a deep copy of the
        ``internal_range_dict`` :class:`~ranges.RangeDict` keys (and therefore will not
        propagate if modified), the RangeResponse values are references, therefore will
        propagate to the ``internal_range_dict`` :class:`~ranges.RangeDict` if modified
        (primarily when ``read``).

        When ``use_windows`` is ``True``, these RangeResponse values are 'simulations'
        (a.k.a. mock/dummy objects) of the range response that would be received from a
        partial content request (they in fact merely came from a streamed GET request).
        """
        # if use_windows:
        #    breakpoint()
        prepared_rangedict = RangeDict()
        internal_rangedict = self._range_windows if use_windows else self._ranges
        for rng_set, rng_response in internal_rangedict.items():
            requested_range = rng_response.request.range
            rng = deepcopy(requested_range)
            # if (rng_response.start, rng_response.end) < 0:
            #    # negative range
            #    ...
            if rng_response.is_consumed():
                continue
            told_is_set = rng_response.is_windowed or ALWAYS_SET_TOLD
            if rng_response_tell := (
                rng_response.told if told_is_set else rng_response.tell()
            ):
                # Access single range (assured by unique RangeResponse values of
                # RangeDict) of singleton rangeset (assured by check_range_integrity)
                rng.start += rng_response_tell
                # if rng.start > rng.end:
                #    breakpoint()
            if rng_response.tail_mark:
                rng.end -= rng_response.tail_mark
                # if rng.start > rng.end:
                #   breakpoint()
            if rng.start > rng.end:
                raise ValueError(f"{rng} has been malformed (rng_response=)")
            prepared_rangedict.update({rng: rng_response})
        return prepared_rangedict

    @property
    def ranges(self):
        """
        Read-only view on the :class:`~ranges.RangeDict` stored in the
        :attr:`~range_streams.stream.RangeStream._ranges` attribute, modifying
        it to account for the bytes consumed (from the head) and tail mark offset
        of where a range was already trimmed to avoid an overlap (from the tail).

        Each :attr:`~range_streams.stream.RangeStream.ranges` :class:`~ranges.RangeDict`
        key is a :class:`~ranges.RangeSet` containing 1 :class:`~ranges.Range`. Check
        this assumption (singleton :class:`~ranges.RangeSet` "integrity") holds and
        retrieve this list of :class:`~ranges.RangeSet` keys in ascending order, as a
        list of :class:`~ranges.Range`.

        Requests are restricted to not re-request already-requested file ranges, so give
        windows onto the underlying range that can be consumed (but the underlying
        :class:~range_streams.response.RangeResponse` will persist and cannot be
        consumed by reading).
        """
        self.check_range_integrity()
        # Unclear if this is necessary but seems consistent to do here:
        if self.single_request:
            # Also check integrity of the range windows
            self.check_range_integrity(use_windows=True)
        if self.freely_requestable:
            # Not limited to a single request
            ranges = self.compute_external_ranges()
        else:
            # Single request limit: can only add a window onto already requested range
            ranges = self.compute_external_ranges(use_windows=True)
        return ranges

    def overlap_whence(
        self, rng: Range, internal: bool = False, use_windows: bool = False
    ) -> int | None:
        if DEBUG_VERBOSE:
            print(f"IN {rng=} {internal=} {use_windows=}")
            for k, v in self._range_windows.items():
                print(f"{k}: {v} ({v.told})")
        internal_rng_dict = self._range_windows if use_windows else self._ranges
        rng_dict = internal_rng_dict if internal else self.ranges
        # if use_windows:
        #    print(rng)
        #    breakpoint()
        if DEBUG_VERBOSE:
            print(f"OUT {rng}")
        return overlap_whence(rng_dict=rng_dict, rng=rng)

    def register_range(
        self,
        rng: Range,
        value: RangeResponse,
        activate: bool = True,
        use_windows: bool = False,
    ):
        if self._length_checked:
            self.check_is_subrange(rng)
        else:
            raise ValueError("Stream length must be set before registering a range")
        if DEBUG_VERBOSE:
            print(f"Hit {rng=} {value=} {activate=} {use_windows=}")
        if (
            self.overlap_whence(rng, internal=False, use_windows=use_windows)
            is not None
        ):
            self.handle_overlap(rng, internal=False, use_windows=use_windows)
        # print(f"Pre: {self._ranges=}")
        # print(f"Adding: {rng=}")
        ranges = self._range_windows if use_windows else self._ranges
        # This is where a previous tail mark is erased (if replacing an overlap)
        ranges.add(rng=rng, value=value)
        if activate:
            self.set_active_range(rng)
        # print(f"Post: {self._ranges=}")

    def set_active_range(self, rng: Range):
        """
        Setter for the active range (through which
        :attr:`~range_streams.stream.RangeStream.active_range_response`
        is also set).
        """
        if self._active_range != rng:
            self._active_range = rng

    @property
    def active_range_response(self) -> RangeResponse:
        """
        Look up the :class:`~range_streams.response.RangeResponse`
        object associated with the currently active range by using
        :attr:`~range_streams.stream.RangeStream._active_range` as the
        :class:`~ranges.Range` key for the internal
        :attr:`~range_streams.stream.RangeStream._ranges`
        :class:`RangeDict`.

        Look it up in the :attr:`~range_streams.stream.RangeStream._ranges`
        :class:`RangeDict` instead if in single request mode.
        """
        internal_rng_dict = self._range_windows if self.single_request else self._ranges
        try:
            return internal_rng_dict[self._active_range]
        except KeyError:
            e_pre = "Cannot get active range response "
            if self._active_range is None:
                raise ValueError(f"{e_pre}(no active range)")
            raise ValueError(f"{e_pre}({self._active_range=}")

    def ext2int(self, ext_rng: Range) -> RangeResponse:
        """
        Given the external range `ext_rng` and the :class:`RangeStream`
        on which it is 'stored' (or rather, computed, in the
        :attr:`~range_streams.stream.RangeStream.ranges` property),
        return the internal :class:`~ranges.Range` stored on the
        :attr:`_ranges` attribute of the
        :attr:`~range_streams.stream.RangeStream`, by looking up the
        shared :class:`~range_streams.response.RangeResponse` value.

        Args:
          ext_rng : A :class:`~ranges.Range` from the 'external'
                    :attr:`~range_streams.stream.RangeStream.ranges`
                    with which to cross-reference in
                    :attr:`~range_streams.stream.RangeStream._ranges`
                    to identify the corresponding 'internal' range.
        """
        rng_response = self.ranges[ext_rng]
        for k, v in self._ranges.items():
            if v == rng_response:
                return k[0].ranges()[0]
        raise ValueError("Looked up a non-existent key in the internal RangeDict")

    def burn_range(self, overlapped_ext_rng: Range):
        """Get the internal range (i.e. without offsets applied from the current read
        position on the range) from the external one (which may differ if the seek position
        has advanced from the start position, usually due to reading bytes from the range).
        Once this internal range has been identified, delete it, and set the
        :attr:`~range_streams.stream.RangeStream._active_range` to the most recent
        (or if the stream becomes empty, set it to ``None``).

        Args:
          overlapped_ext_rng : the overlapped external range
        """
        internal_rng = self.ext2int(ext_rng=overlapped_ext_rng)
        self._ranges.remove(internal_rng)
        # set `_active_range` to most recently registered internal range or None if empty
        self.set_active_range(most_recent_range(self, internal=True))

    def handle_overlap(
        self,
        rng: Range,
        internal: bool = False,
        use_windows: bool = False,
    ) -> None:
        """
        Handle overlaps with a given pruning level:

        0. "replant" ranges overlapped at the head with fresh, disjoint ranges 'downstream'
           or mark their tails to effectively truncate them if overlapped at the tail
        1. "burn" existing ranges overlapped anywhere by the new range
        2. "strict" will throw a :class:`ValueError`
        """
        internal_rng_dict = self._range_windows if use_windows else self._ranges
        ranges = internal_rng_dict if internal else self.ranges
        if self.pruning_level not in range(3):
            raise ValueError("Pruning level must be 0, 1, or 2")
        # print(f"Handling {rng=} with {self.pruning_level=}")
        if rng.isempty():
            raise ValueError("Range overlap not detected as the range is empty")
        if self.pruning_level == 2:  # 2: strict
            raise ValueError(
                "Range overlap not registered due to strict pruning policy"
            )
        rng_min, rng_max = range_termini(rng)
        if rng not in ranges:
            # May be partially overlapping
            has_min, has_max = (pos in ranges for pos in [rng_min, rng_max])
            if has_min:
                # if has_min and has_max:
                #    print("Partially contained on multiple ranges")
                # T: Overlap at  tail   of pre-existing RangeResponse truncates that tail
                # M: Overlap at midbody of pre-existing RangeResponse truncates that tail
                overlapped_rng = get_range_containing(rng_dict=ranges, position=rng_min)
                # print(f"T/M {overlapped_rng=}")
                if self.pruning_level == 1:  # 1: burn
                    self.burn_range(overlapped_ext_rng=overlapped_rng)
                else:  # 0: replant
                    o_rng_min, o_rng_max = range_termini(overlapped_rng)
                    intersect_len = o_rng_max - rng_min + 1
                    ranges[rng_min].tail_mark += intersect_len
            elif has_max:
                # H: Overlap at head of pre-existing RangeResponse is replanted or burnt
                overlapped_rng = get_range_containing(rng_dict=ranges, position=rng_max)
                # print(f"H {overlapped_rng=}")
                if self.pruning_level == 1:  # 1: burn
                    self.burn_range(overlapped_ext_rng=overlapped_rng)
                else:  # 0: replant
                    o_rng_min, o_rng_max = range_termini(overlapped_rng)
                    intersect_len = rng_max - o_rng_min + 1
                    # For now, simply throw away: read `size=intersect_len` bytes of response,
                    # consequently `tell` will trim the head computed in `ranges` property
                    # _ = ranges[rng_max].read(intersect_len)
                    self.burn_range(overlapped_ext_rng=overlapped_rng)
                    if (new_o_rng_min := o_rng_min + intersect_len) > rng_max:
                        new_o_rng_max = (
                            o_rng_max  # (I can't think of exceptions to this?)
                        )
                        new_o_rng = Range(new_o_rng_min, new_o_rng_max + 1)
                        self.add(
                            new_o_rng
                        )  # head-overlapped range has been 'replanted'
            else:
                info = f"{rng=} and {ranges=}"
                raise ValueError(f"Range overlap not detected at termini {info}")
        else:  # HTT: Full overlap with an existing range ("Head To Tail")
            overlapped_rng = get_range_containing(rng_dict=ranges, position=rng_max)
            # Fully overlapped ranges would be exhausted if read, so delete regardless of
            # whether pruning policy is "replant"/"burn" (i.e. can't replant empty range)
            # print(f"HTT {overlapped_rng=}")
            self.burn_range(overlapped_ext_rng=overlapped_rng)

    @property
    def total_bytes(self) -> int | None:
        """
        The total number of bytes (i.e. the length) of the file being streamed.
        """
        return self._length if self._length_checked else None

    def isempty(self) -> bool:
        """
        Whether the internal :attr:`~range_streams.stream.RangeStream._ranges`
        :class:`~ranges.RangeDict` is empty (contains no range-RangeResponse key-value
        pairs).
        """
        return self.ranges.isempty()

    @property
    def spanning_range(self) -> Range:
        return Range(0, 0) if self.isempty() else range_span(self.list_ranges())

    @property
    def total_range(self) -> Range:
        try:
            return Range(0, self._length)
        except Exception:  # messy exception avalanche
            raise AttributeError("Cannot use total_range before setting _length")

    @property
    def name(self) -> str:
        return Path(self.url).name

    @property
    def domain(self) -> str:
        return urlparse(self.url).netloc

    def tell(self) -> int:
        return self.active_range_response.tell()

    def read(self, size=None) -> bytes:
        return self.active_range_response.read(size=size)

    def seek(self, position, whence=SEEK_SET) -> None:
        self.active_range_response.seek(position=position, whence=whence)

    def send_request(self, byte_range: Range) -> RangeRequest:
        if self.client_is_async:
            raise NotImplementedError("Async client support WIP")
        return RangeRequest(
            byte_range=byte_range,
            url=self.url,
            client=self.client,
        )

    def simulate_request(
        self, byte_range: Range, parent_range_request: RangeRequest | None = None
    ) -> RangeRequest:
        """
        Simulate the :class:`~range_streams.request.RangeRequest` obtained from a
        partial content request for ``byte_range`` on the stream's URL through a
        "window" on ``range_request`` (expected to be a streamed GET request for the
        full file range).

        If no ``parent_range_request`` is provided, it is assumed to be the one on the
        :class:`~range_streams.response.RangeResponse` in the internal
        :attr:`~range_streams.stream.RangeStream._ranges` :class:`~ranges.RangeDict`

        Args:
          byte_range           : The :class:`~ranges.Range` to simulate a partial
                                 content request for.
          parent_range_request : The :class:`~range_streams.request.RangeRequest` over
                                 which to use a "window" to simulate the range request.
        """
        if parent_range_request is None:
            access_pos = byte_range.start
            if access_pos not in self._ranges:
                msg = f"{access_pos} is not in internal RangeDict\n{self._ranges=}"
                raise ValueError(msg)
            parent_range_response = self._ranges[access_pos]
            parent_range_request = parent_range_response.request
        return RangeRequest.windowed_request(
            byte_range=byte_range,
            range_request=parent_range_request,
            tail_mark=parent_range_response.tail_mark,
        )

    def get_monostream(self) -> None:
        """
        Send a streaming GET request with an open-ended ``content-range`` header, to
        obtain the total range. Suitable for higher performance (to avoid repeated
        requests on the :class:`~range_streams.stream.RangeStream` which accrue a time
        cost).

        Called at initialisation (within the first) when ``single_request`` is passed
        to :class:`~range_streams.stream.RangeStream` as ``True``.
        """
        rng_h = range_header(rng=Range(0, 0))  # Empty range -> open-ended range header
        req = self.client.build_request(method="GET", url=self.url, headers=rng_h)
        resp = self.client.send(request=req, stream=True)
        resp.raise_for_status()
        total_length = self.check_response_length(headers=resp.headers, req=req.method)
        self.set_length(length=total_length)

        # This is where self.send_request would give a RangeRequest...
        range_req = RangeRequest.from_get_stream(
            byte_range=self.total_range,
            client=self.client,
            req=req,
            resp=resp,
        )

        # then just use the req to create a RangeResponse and register as usual
        resp = RangeResponse(stream=self, range_request=range_req, range_name="")
        self.register_range(
            rng=self.total_range,
            value=resp,
            activate=False,  # Don't set the active range as this is 'internal'
            use_windows=False,
        )

    def send_head_request(self) -> None:
        """
        Send a 'plain' HEAD request without range headers, to check the total content
        length without creating a RangeRequest (simply discard the response as it can
        only be associated with the empty range, which cannot be stored in a
        :class:`~ranges.RangeDict`), raising for status ASAP.
        To be used when initialised with an empty byte range.
        If the :attr:`range_streams.stream.RangeStream.client` is asynchronous, use
        a synchronous client (created for this single request).
        """
        req = self.sync_client.build_request(method="HEAD", url=self.url)
        resp = self.sync_client.send(request=req)
        resp.raise_for_status()
        total_length = self.check_response_length(headers=resp.headers, req=req.method)
        self.set_length(length=total_length)

    def check_response_length(self, headers: dict[str, str], req: str) -> int:
        """
        Return the length of the response from its ``content-length`` header (after
        checking it contains this header, else raising :class:`KeyError`), as an integer.

        Args:
          headers : The response headers
          req     : The request method (to be reported in any :class:`KeyError` raised)
        """
        total_length = detect_header_value(
            headers=headers, key="content-length", source=f"{req} request response"
        )
        return int(total_length)

    def set_length(self, length: int) -> None:
        self._length = length
        self._length_checked = True

    def list_ranges(self) -> list[Range]:
        """
        Retrieve ascending order list of RangeSet keys, as a :class:`list` of
        :class:`~ranges.Range`.

        The :class:`~ranges.RangeSet` to :class:`~ranges.Range` transformation is
        permitted because the :attr:`~range_streams.stream.RangeStream.ranges`
        property method begins by checking range integrity, which requires
        each :class:`~ranges.RangeSet` to be a singleton set (of a single
        :class:`~ranges.Range`).

        If ``activate`` is ``True`` (the default), the range will be made the active range
        of the :class:`~range_streams.stream.RangeStream` upon being
        registered (if it meets the criteria for registration).

        If ``pruning_level`` is ``0`` then overlaps are handled using a "replant" policy
        (redefine and overwrite the existing range to be disjoint when the new range
        would overlap it), if it's ``1`` they are handled with a "burn" policy (simply
        dispose of the existing range to eliminate any potential overlap), and if
        it's ``2`` using a "strict" policy (raising errors upon detecting overlap).
        """
        return [rngset.ranges()[0] for rngset in self.ranges.ranges()]

    def add(
        self,
        byte_range: Range | tuple[int, int] = Range("[0, 0)"),
        activate: bool = True,
        name: str = "",
    ) -> None:
        """
        Add a range to the stream. If it is empty and the length of the stream has not
        already been determined, this will initiate a HEAD request to check the file's
        total size. In all other cases, only add the :class:`~ranges.Range` to the
        :class:`~ranges.RangeDict` of :attr:`~range_streams.stream.RangeStream.ranges`,
        set up a streaming partial content GET request, but do not try to read any
        bytes from it (so response data will be downloaded upon creation).

        The ``byte_range`` can be specified as either a :class:`~ranges.Range`
        object, or 2-tuple of integers (``(start, end)``), interpreted
        either way as a half-closed interval ``[start, end)``, as given by
        Python's built-in :class:`range`.

        If ``activate`` is ``True``, make this range the active range upon adding it
        to the stream (allowing access to the associated response through the
        :attr:`~range_streams.stream.RangeStream.active_range_response` property).

        If a ``name`` is provided (used in subclasses where the stream is an archive
        with individually named files within it), assign this name to the
        :class:`~range_streams.response.RangeResponse` (as its ``range_name`` argument).

        Args:
          byte_range : (:class:`~ranges.Range` | ``tuple[int,int]``) The range
                       of positions on the file to be requested and stored in
                       the :class:`~ranges.RangeDict` on
                       :attr:`~range_streams.stream.RangeStream.ranges`
          activate   : (:class:`bool`) Whether to make this newly added
                       :class:`~ranges.Range` the active range on the stream upon
                       creating it.
          name       : (:class:`str`) A name (default: ``''``) to give to the range.
        """
        # TODO remove edge case handling for empty range, now handled separately at init
        byte_range = validate_range(byte_range=byte_range, allow_empty=True)
        # Do not request an empty range if total length already checked (at init)
        if not self._length_checked and byte_range.isempty():
            if self.single_request:
                self.get_monostream()
            else:
                self.send_head_request()
        elif not byte_range.isempty():
            if self.single_request:
                # register a window onto the original range in the ``_ranges``
                # RangeDict rather than add a new range entry to the dict (which would
                # A) clash with the single entire range B) require another request
                req = self.simulate_request(byte_range=byte_range)
                resp = RangeResponse(stream=self, range_request=req, range_name=name)
                self.register_range(
                    rng=byte_range,
                    value=resp,
                    activate=activate,
                    use_windows=True,
                )
            else:
                req = self.send_request(byte_range=byte_range)
                if not self._length_checked:
                    self.set_length(length=req.total_content_length)
                if byte_range in ranges_in_reg_order(self.ranges):
                    pass  # trivial no-op when adding a range that already exists
                elif not byte_range.isempty():
                    # bytes are available in the RangeRequest.response stream
                    resp = RangeResponse(
                        stream=self, range_request=req, range_name=name
                    )
                    self.register_range(
                        rng=byte_range,
                        value=resp,
                        activate=activate,
                        use_windows=False,
                    )
