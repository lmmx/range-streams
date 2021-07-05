from __future__ import annotations
import httpx
from ranges import Range
from typing import Generator
from .http_utils import range_header

__all__ = ["RangeRequest"]

class RangeRequest:
    """
    Store a GET request and the response stream while keeping a reference to
    the client that spawned it, providing an overridable `_iterator` attribute
    [by default giving access to `iter_raw()`] on the underlying response,
    suitable for `RangeResponse` to wrap in a `io.BytesIO` buffered stream.
    """
    def __init__(self, client: httpx.Client, url: str, byte_range: Range):
        self.range = byte_range
        self.url = url
        self.client = client
        self.setup_stream()
        self.content_range = self.content_range_header()
        self._iterator = self.iter_raw()

    @property
    def range_header(self):
        return range_header(self.range)

    def setup_stream(self) -> None:
        """
        `client.stream("GET", url)` but leave the stream to be manually closed
        rather than using a context manager
        """
        h = self.range_header
        self.request = self.client.build_request(method="GET", url=self.url, headers=h)
        self.response = self.client.send(request=self.request, stream=True)

    def content_range_header(self) -> str:
        """
        Validate request was range request by presence of `content-range` header
        """
        try:
            return self.response.headers["content-range"]
        except KeyError as e:
            raise KeyError(f"Response was missing 'content-range' header""\n{e}")

    @property
    def total_content_length(self) -> int:
        return int(self.content_range.split("/")[-1])

    def iter_raw(self) -> Generator[bytes]:
        return self.response.iter_raw()

    def close(self) -> None:
        if not self.response.is_closed:
            self.response.close()