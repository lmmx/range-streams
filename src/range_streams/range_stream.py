r"""mod:`range_streams.range_stream` exposes a class
`RangeStream`, whose key property (once initialised) is `ranges`,
which provides a `RangeDict` comprising the ranges of
the file being streamed.

The method `RangeStream.add` will request further ranges,
and (unlike the other methods in this module) will accept
a tuple of two integers as its argument (`byte_range`).

See `help(RangeStream)` for more information.
"""

from __future__ import annotations

from copy import deepcopy
from io import SEEK_SET
from pathlib import Path
from urllib.parse import urlparse

import httpx
from ranges import Range, RangeDict

from .overlaps import handle_overlap, overlap_whence
from .range_request import RangeRequest
from .range_response import RangeResponse
from .range_utils import range_max, range_span, ranges_in_reg_order, validate_range

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

    Both the `RangeStream.__init__` and `RangeStream.add`
    methods support the specification of a range interval as either a
    tuple of two integers or a `Range` from the mod:`python-ranges`
    (an external requirement installed alongside this package). Either
    way, the interval created is interpreted to be the standard Python
    convention of a half-open interval `[start,stop)`.
    """

    _length_checked = False
    _active_range = None

    def __init__(
        self,
        url: str,
        client: httpx.Client,
        byte_range: Range | tuple[int, int] = Range("[0, 0)"),
        pruning_level: int = 0,
    ):
        self.url = url
        self.client = client
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
        "Every `RangeSet` in the `_ranges: RangeDict` keys must contain 1 Range each"
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
        Modifying the `_ranges` attribute to account for the bytes consumed
        (from the head) and tail mark offset of where a range was already
        trimmed to avoid an overlap (from the tail).

        While the RangeSet keys are a deep copy of the _ranges RangeDict keys (and
        therefore will not propagate if modified), the RangeResponse values are
        references, therefore will propagate to the `_ranges` RangeDict if modified.
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
        Read-only view on the RangeDict stored in the `_ranges` attribute, modifying
        it to account for the bytes consumed (from the head) and tail mark offset
        of where a range was already trimmed to avoid an overlap (from the tail).

        Each `ranges` RangeDict key is a RangeSet containing 1 Range. Check
        this assumption (singleton RangeSet "integrity") holds and retrieve
        this list of RangeSet keys in ascending order, as a list of `Range`s.
        """
        self.check_range_integrity()
        return self.compute_external_ranges()

    def overlap_whence(self, rng: Range, internal: bool = False) -> int | None:
        return overlap_whence(self, rng, internal=internal)

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
            self._active_range = rng
        # print(f"Post: {self._ranges=}")

    @property
    def active_range_response(self):
        try:
            return self._ranges[self._active_range]
        except KeyError:
            e_pre = "Cannot get active range response "
            if self._active_range is None:
                raise ValueError(f"{e_pre}(no active range)")
            raise ValueError(f"{e_pre}({self._active_range=}")

    def handle_overlap(self, rng: Range, internal: bool = False) -> None:
        handle_overlap(self, rng, internal=internal)

    @property
    def total_bytes(self) -> int | None:
        return self._length if self._length_checked else None

    def isempty(self) -> bool:
        return self._ranges.isempty()

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
        return RangeRequest(byte_range=byte_range, url=self.url, client=self.client)

    def set_length(self, length: int) -> None:
        self._length = length
        self._length_checked = True

    def list_ranges(self) -> list[Range]:
        """
        Retrieve ascending order list of RangeSet keys, as a list of `Range`s.

        The RangeSet to Range transformation is permitted because the `ranges`
        property method begins by checking range integrity, which requires
        each RangeSet to be a singleton set (of a single Range).

        If `activate` is True (the default), the range will be made the active range
        of the RangeStream upon being registered (if it meets the criteria for
        registration).

        If `pruning_level` is 0 then overlaps are handled using a "replant" policy
        (redefine and overwrite the existing range to be disjoint when the new range
        would overlap it), if it's 1 they are handled with a "burn" policy (simply
        dispose of the existing range to eliminate any potential overlap), and if
        it's 2 using a "strict" policy (raising errors upon detecting overlap).
        """
        return [rngset.ranges()[0] for rngset in self.ranges.ranges()]

    def add(
        self,
        byte_range: Range | tuple[int, int] = Range("[0, 0)"),
        activate: bool = True,
    ) -> None:
        byte_range = validate_range(byte_range=byte_range, allow_empty=True)
        # Do not send a request for an empty range if total length already checked
        if not self._length_checked or not byte_range.isempty():
            req = self.send_request(byte_range)
            if not self._length_checked:
                self.set_length(req.total_content_length)
            if byte_range in ranges_in_reg_order(self.ranges):
                pass  # trivial no-op when adding a range that already exists
            elif not byte_range.isempty():
                # bytes are available in the RangeRequest.response stream
                resp = RangeResponse(stream=self, range_request=req)
                self.register_range(
                    rng=byte_range,
                    value=resp,
                    activate=activate,
                )
