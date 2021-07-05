from __future__ import annotations
from io import BytesIO, SEEK_SET, SEEK_END
from ranges import Range, RangeSet, RangeDict
from .range_utils import validate_range, range_span # range_max
from .range_response import RangeResponse
from .range_request import RangeRequest
from .overlaps import handle_overlap
from sys import stderr
from pathlib import Path
from urllib.parse import urlparse

__all__ = ["RangeStream"]


class RangeStream:
    _length_checked = False
    _active_range = None

    def __init__(
        self,
        url: str,
        client: httpx.Client,
        byte_range: Range | tuple[int, int] = Range("[0, 0)"),
    ):
        self.url = url
        self.client = client
        self._ranges = RangeDict()
        self.handle_byte_range(byte_range=byte_range)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__} ⠶ {self.__ranges_repr__()} @@ "
            f"'{self.name}' from {self.domain}"
        )

    def __ranges_repr__(self) -> str:
        return ", ".join(map(str, self.list_ranges()))

    def check_is_subrange(self, rng: Range):
        if rng not in self.total_range:
            raise ValueError(f"{rng} is not a sub-range of {self.total_range}")

    def register_range(self, rng: Range, value: RangeResponse):
        if self._length_checked:
            self.check_is_subrange(rng)
        else:
            raise ValueError("Stream length must be set before registering a range")
        if rng in self._ranges:
            self.handle_overlap(rng)
        self._ranges.add(rng=rng, value=value)
        if self._active_range is None:
            self._active_range = rng

    def handle_overlap(self, rng: Range):
        handle_overlap(self, rng)
        raise NotImplementedError("Range overlap detected")

    @property
    def total_bytes(self) -> int | None:
        return self._length if self._length_checked else None

    def isempty(self):
        return self._ranges.isempty()

    @property
    def spanning_range(self) -> Range:
        return Range(0,0) if self.isempty() else range_span(self.list_ranges())

    @property
    def total_range(self) -> Range:
        try:
            return Range(0, self._length)
        except AttributeError:
            raise AttributeError("Cannot use total_range before setting _length")

    @property
    def name(self) -> str:
        return Path(self.url).name

    @property
    def domain(self) -> str:
        return urlparse(self.url).netloc

    def make_iterator(self, target_range: Range):
        iterator = request_iterator(target_range)

    def _load_all(self):
        self._bytes.seek(0, SEEK_END)
        for chunk in self._iterator:
            self._bytes.write(chunk)

    def _load_until(self, goal_position):
        current_position = self._bytes.seek(0, SEEK_END)
        while current_position < goal_position:
            try:
                current_position += self._bytes.write(next(self._iterator))
            except StopIteration:
                break

    def tell(self):
        return self._bytes.tell()

    def read(self, size=None):
        left_off_at = self._bytes.tell()
        if size is None:
            self._load_all()
        else:
            goal_position = left_off_at + size
            self._load_until(goal_position)

        self._bytes.seek(left_off_at)
        return self._bytes.read(size)

    def seek(self, position, whence=SEEK_SET):
        if whence == SEEK_END:
            if self._length_checked:
                # Make first range with negative seek position
                pass
            else:
                # Calculate seek position and check if in RangeDict
                pass
        self._bytes.seek(position, whence)

    def send_request(self, byte_range: Range) -> RangeRequest:
        return RangeRequest(client=self.client, url=self.url, byte_range=byte_range)

    def set_length(self, length: int):
        self._length = length
        self._length_checked = True

    def check_range_integrity(self) -> None:
        "Every `RangeSet` in the `_ranges: RangeDict` keys must contain 1 Range each"
        if sum(len(rs._ranges) - 1 for rs in self._ranges.ranges()) != 0:
            bad_rs = [rs for rs in self._ranges.ranges() if len(rs._ranges) - 1 != 0]
            raise ValueError(f"Each RangeSet must contain 1 Range: found {bad_rs=}")
    
    def list_ranges(self) -> list[Range]:
        """
        Each `_ranges` RangeDict key is a RangeSet containing 1 Range. Check
        this assumption (singleton RangeSet "integrity") holds and retrieve
        this list of RangeSet keys in ascending order, as a list of `Range`s.
        """
        self.check_range_integrity()
        return [rngset.ranges()[0] for rngset in self._ranges.ranges()]

    def handle_byte_range(
        self, byte_range: Range | tuple[int, int] = Range("[0, 0)")
    ) -> None:
        byte_range = validate_range(byte_range=byte_range, allow_empty=True)
        # Do not send a request for an empty range if total length already checked
        if not self._length_checked or not byte_range.isempty():
            req = self.send_request(byte_range)
            if not self._length_checked:
                self.set_length(req.total_content_length)
            if not byte_range.isempty():
                # bytes are available in the RangeRequest.response stream
                resp = RangeResponse(stream=self, range_request=req)
                self.register_range(rng=byte_range, value=resp)
        # TODO: handle overlaps
        #elif :
        #    r_max = range_max(byte_range)
