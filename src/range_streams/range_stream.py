from __future__ import annotations
from io import BytesIO, SEEK_SET, SEEK_END
from ranges import Range, RangeSet, RangeDict

__all__ = ["RangeStream"]


class RangeStream:
    _length_checked = False

    def __init__(
        self,
        url: str,
        client: bool,
        byte_range: Range | tuple[int, int] = Range("[0, 0)"),
    ):
        self._url = url
        self._client = client
        self._ranges = RangeDict()
        self._bytes = BytesIO()

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
