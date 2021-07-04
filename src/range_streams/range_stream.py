from __future__ import annotations
from io import BytesIO, SEEK_SET, SEEK_END
from ranges import Range, RangeSet, RangeDict
from .range_utils import range_max, check_range
from .range_response import RangeResponse
from .range_map import RangeMap
from .range_request import RangeRequest

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
        # TODO replace RangeDict with RangeMap if repr is fixable?
        self._ranges = RangeDict()# RangeMap(parent_stream=self)
        self.handle_byte_range(byte_range=byte_range)

    def register_range(self, rng: Range, value: RangeResponse):
        self._ranges.register_range(rng=rng)
        if self._active_range is None:
            _active_range = rng

    @property
    def total_bytes(self) -> int | None:
        return self._length if self._length_checked else None

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

    def handle_byte_range(
        self, byte_range: Range | tuple[int, int] = Range("[0, 0)")
    ) -> None:
        # Validate byte_range and convert to `[a,b)` Range if given as integer tuple
        byte_range = check_range(byte_range=byte_range, allow_empty=True)
        # Do not send a request for an empty range if total length already checked
        if not self._length_checked or not byte_range.isempty():
            req = self.send_request(byte_range)
            if not self._length_checked:
                self._length = req.total_content_length
            if not byte_range.isempty():
                # bytes are available in the RangeRequest.response stream
                resp = RangeResponse(stream=self, range_request=req)
                self.register_range(rng=byte_range, value=resp)
        # TODO: handle overlaps
        #elif :
        #    r_max = range_max(byte_range)
