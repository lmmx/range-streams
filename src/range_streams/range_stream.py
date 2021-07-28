r""":mod:`range_streams.range_stream` exposes a class
:py:func:`RangeStream`, whose key property (once initialised) is
:attr:`~range_streams.range_stream.RangeStream.ranges`,
which provides a :class:`ranges.RangeDict` comprising the ranges of
the file being streamed.

The method :py:func:`RangeStream.add` will request further ranges,
and (unlike the other methods in this module) will accept
a tuple of two integers as its argument (``byte_range``).
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

from .http_utils import detect_header_value
from .overlaps import get_range_containing, overlap_whence
from .range_request import RangeRequest
from .range_response import RangeResponse
from .range_utils import (
    most_recent_range,
    range_max,
    range_span,
    range_termini,
    ranges_in_reg_order,
    validate_range,
)

__all__ = ["RangeStream"]


class RangeStream:
    """
    A class representing a file being streamed from a server which supports
    range requests, with the `ranges` property providing a list of those
    intervals requested so far (and not yet exhausted).

    When the class is initialised its length checked upon the first range
    request, and the client provided is not closed (you must handle this
    yourself). Further ranges may be requested on the `RangeStream` by
    calling `add`.

    Both the :meth:`~range_streams.range_stream.RangeStream.__init__` and
    :meth:`~range_streams.range_stream.RangeStream.add` methods support
    the specification of a range interval as either a tuple of two
    integers or a :class:`~ranges.Range` from the :mod:`python-ranges` package
    (an external requirement installed alongside this package). Either
    way, the interval created is interpreted to be the standard Python
    convention of a half-open interval ``[start,stop)``.
    """

    _length_checked: bool = False
    _active_range: Range | None = None

    _ranges: RangeDict
    """
    `'Internal'` ranges attribute. Start position is not affected by
    reading in bytes from the :class:`RangeResponse` (unlike the
    'externa' :attr:`ranges` property)
    """

    def __init__(
        self,
        url: str,
        client=None,  # don't hint httpx.Client (Sphinx gives error)
        byte_range: Range | tuple[int, int] = Range("[0, 0)"),
        pruning_level: int = 0,
    ):
        self.url = url
        self.client = client
        if self.client is None:
            self.client = httpx.Client()
        self.pruning_level = pruning_level
        self._ranges = RangeDict()
        self.add(byte_range=byte_range)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__} ⠶ {self.__ranges_repr__()} @@ "
            f"'{self.name}' from {self.domain}"
        )

    # @property
    # def _ranges(self):
    #    return self.__ranges__

    # @_ranges.setter
    # def _ranges(self, val):
    #    self.__ranges__ = val

    def __ranges_repr__(self) -> str:
        return ", ".join(map(str, self.list_ranges()))

    def check_is_subrange(self, rng: Range):
        if rng not in self.total_range:
            raise ValueError(f"{rng} is not a sub-range of {self.total_range}")

    def check_range_integrity(self) -> None:
        """
        Every :class:`~ranges.RangeSet` in the
        :attr:`~range_streams.range_stream.RangeStream._ranges``
        :class:`~ranges.RangeDict` keys must contain 1 :class:`~ranges.Range` each
        """
        if sum(len(rs._ranges) - 1 for rs in self._ranges.ranges()) != 0:
            bad_rs = [rs for rs in self._ranges.ranges() if len(rs._ranges) - 1 != 0]
            for rset in bad_rs:
                for rng in rset:
                    rng_resp = self._ranges[rng.start]
                    rng_max = range_max(rng)
                    if rng_resp.tell() > rng_max:
                        rset.discard(rng)  # discard subrange
                if len(rset.ranges()) < 2:
                    bad_rs.remove(rset)
            if bad_rs:
                raise ValueError(f"Each RangeSet must contain 1 Range: found {bad_rs=}")

    def compute_external_ranges(self) -> RangeDict:
        """
        Modifying the :attr:`~range_streams.range_stream.RangeStream._ranges`
        attribute to account for the bytes consumed (from the head)
        and tail mark offset of where a range was already trimmed to avoid
        an overlap (from the tail).

        While the :class:`~ranges.RangeSet` keys are a deep copy of the
        :attr:`~range_streams.range_stream.RangeStream._ranges`
        :class:`~ranges.RangeDict` keys (and therefore will not propagate if modified),
        the RangeResponse values are references, therefore will propagate to the
        :attr:`~range_streams.range_stream.RangeStream._ranges`
        :class:`~ranges.RangeDict` if modified.
        """
        prepared_rangedict = RangeDict()
        internal_rangedict = self._ranges.items()
        for rng_set, rng_response in internal_rangedict:
            requested_range = rng_response.request.range
            rng = deepcopy(requested_range)
            # if (rng_response.start, rng_response.end) < 0:
            #    # negative range
            #    ...
            if rng_response.is_consumed():
                continue
            if rng_response_tell := rng_response.tell():
                # Access single range (assured by unique RangeResponse values of
                # RangeDict) of singleton rangeset (assured by check_range_integrity)
                rng.start += rng_response_tell
            if rng_response.tail_mark:
                rng.end -= rng_response.tail_mark
            prepared_rangedict.update({rng: rng_response})
        return prepared_rangedict

    @property
    def ranges(self):
        """
        Read-only view on the :class:`~ranges.RangeDict` stored in the
        :attr:`~range_streams.range_stream.RangeStream._ranges` attribute, modifying
        it to account for the bytes consumed (from the head) and tail mark offset
        of where a range was already trimmed to avoid an overlap (from the tail).

        Each :attr:`~range_streams.range_stream.RangeStream.ranges` :class:`~ranges.RangeDict`
        key is a :class:`~ranges.RangeSet` containing 1 :class:`~ranges.Range`. Check
        this assumption (singleton :class:`~ranges.RangeSet` "integrity") holds and retrieve
        this list of :class:`~ranges.RangeSet` keys in ascending order, as a list of
        :class:`~ranges.Range`.
        """
        self.check_range_integrity()
        return self.compute_external_ranges()

    def overlap_whence(self, rng: Range, internal: bool = False) -> int | None:
        rng_dict = self._ranges if internal else self.ranges
        return overlap_whence(rng_dict, rng)

    def register_range(
        self,
        rng: Range,
        value: RangeResponse,
        activate: bool = True,
    ):
        if self._length_checked:
            self.check_is_subrange(rng)
        else:
            raise ValueError("Stream length must be set before registering a range")
        if self.overlap_whence(rng, internal=False) is not None:
            self.handle_overlap(rng, internal=False)
        # print(f"Pre: {self._ranges=}")
        # print(f"Adding: {rng=}")
        self._ranges.add(rng=rng, value=value)
        if activate:
            self.set_active_range(rng)
        # print(f"Post: {self._ranges=}")

    def set_active_range(self, rng: Range):
        """
        Setter for the active range (through which active_range_response is also set).
        """
        if self._active_range != rng:
            self._active_range = rng

    @property
    def active_range_response(self) -> RangeResponse:
        """Look up the :class:`RangeResponse` object associated with the
        currently active range by using
        :attr:`~range_streams.range_stream.RangeStream._active_range` as the
        :class:`Range` key for the internal
        :attr:`~range_streams.range_stream.RangeStream._ranges` :class:`RangeDict`.
        """
        try:
            return self._ranges[self._active_range]
        except KeyError:
            e_pre = "Cannot get active range response "
            if self._active_range is None:
                raise ValueError(f"{e_pre}(no active range)")
            raise ValueError(f"{e_pre}({self._active_range=}")

    def ext2int(self, ext_rng: Range) -> RangeResponse:
        """Given the external range `ext_rng` and the :class:`RangeStream`
        on which it is 'stored' (or rather, computed, in the
        :attr:`~range_streams.range_stream.RangeStream.ranges` property),
        return the internal :class:`~ranges.Range` stored on the
        :attr:`_ranges` attribute of the
        :attr:`~range_streams.range_stream.RangeStream`, by looking up the
        shared :class:`~range_streams.range_response.RangeResponse` value.

        Args:
          ext_rng : A :class:`ranges.Range` from the 'external'
                    :attr:`~range_streams.range_stream.RangeStream.ranges`
                    with which to cross-reference in
                    :attr:`~range_streams.range_stream.RangeStream._ranges`
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
        :attr:`~range_streams.range_stream.RangeStream._active_range` to the most recent
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
    ) -> None:
        """
        Handle overlaps with a given pruning level:

        0. "replant" ranges overlapped at the head with fresh, disjoint ranges 'downstream'
           or mark their tails to effectively truncate them if overlapped at the tail
        1. "burn" existing ranges overlapped anywhere by the new range
        2. "strict" will throw a :class:`ValueError`
        """
        ranges = self._ranges if internal else self.ranges
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
        Whether the internal :attr:`~range_streams.range_stream.RangeStream._ranges`
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
        return RangeRequest(
            byte_range=byte_range,
            url=self.url,
            client=self.client,
        )

    def send_head_request(self) -> None:
        """
        Send a 'plain' HEAD request without range headers, to check the total content
        length without creating a RangeRequest (simply discard the response as it can
        only be associated with the empty range, which cannot be stored in a
        :class:`~ranges.RangeDict`), raising for status ASAP.
        To be used when initialised with an empty byte range.
        """
        req = self.client.build_request("HEAD", self.url)
        resp = self.client.send(request=req)
        resp.raise_for_status()
        key = "content-length"
        try:
            total_length = detect_header_value(headers=resp.headers, key=key)
        except KeyError as exc:
            raise KeyError(f"HEAD request response was missing '{key}' header") from exc
        self.set_length(int(total_length))

    def set_length(self, length: int) -> None:
        self._length = length
        self._length_checked = True

    def list_ranges(self) -> list[Range]:
        """
        Retrieve ascending order list of RangeSet keys, as a :class:`list` of
        :class:`~ranges.Range`.

        The :class:`~ranges.RangeSet` to :class:`~ranges.Range` transformation is
        permitted because the :attr:`~range_streams.range_stream.RangeStream.ranges`
        property method begins by checking range integrity, which requires
        each :class:`~ranges.RangeSet` to be a singleton set (of a single
        :class:`~ranges.Range`).

        If ``activate`` is ``True`` (the default), the range will be made the active range
        of the :class:`~range_streams.range_stream.RangeStream` upon being
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
        # TODO remove edge case handling for empty range, now handled separately at init
        byte_range = validate_range(byte_range=byte_range, allow_empty=True)
        # Do not request an empty range if total length already checked
        if not self._length_checked and byte_range.isempty():
            self.send_head_request()
        elif not byte_range.isempty():
            req = self.send_request(byte_range)
            if not self._length_checked:
                self.set_length(req.total_content_length)
            if byte_range in ranges_in_reg_order(self.ranges):
                pass  # trivial no-op when adding a range that already exists
            elif not byte_range.isempty():
                # bytes are available in the RangeRequest.response stream
                resp = RangeResponse(stream=self, range_request=req, range_name=name)
                self.register_range(
                    rng=byte_range,
                    value=resp,
                    activate=activate,
                )
