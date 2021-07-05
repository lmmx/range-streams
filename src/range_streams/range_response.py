from __future__ import annotations
from io import BytesIO, SEEK_SET, SEEK_END
from ranges import Range, RangeDict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .range_stream import RangeStream

__all__ = ["RangeResponse"]

class RangeResponse:
    def __init__(
        self,
        stream: RangeStream,
        range_request: RangeRequest
    ):
        self.parent_stream = stream
        self.request = range_request
        self._bytes = BytesIO()

    def __repr__(self):
        return f'{self.__class__.__name__} ⠶ <{self.request.range} @ "{self.url}">'

    @property
    def _iterator(self):
        return self.request._iterator

    @property
    def client(self):
        return self.request.client

    @property
    def url(self) -> str:
        return self.parent_stream.url

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
            self._load_all()
        self._bytes.seek(position, whence)
