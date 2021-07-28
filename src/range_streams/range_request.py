from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

MYPY = False  # when using mypy will be overrided as True
if TYPE_CHECKING:  # pragma: no cover
    from ranges import Range
if MYPY or not TYPE_CHECKING:  # pragma: no cover
    import httpx  # avoid importing to Sphinx type checker

from .http_utils import PartialContentStatusError, detect_header_value, range_header

__all__ = ["RangeRequest"]


class RangeRequest:
    """
    Store a GET request and the response stream while keeping a reference to
    the client that spawned it, providing an overridable
    :attr:`~range_streams.range_response.RangeResponse._iterator` attribute
    [by default giving access to
    :meth:`~range_streams.range_response.RangeResponse.iter_raw`] on the
    underlying ``httpx.Response``, suitable for
    :class:`~range_streams.range_response.RangeResponse`
    to wrap in a :class:`io.BytesIO` buffered stream.
    """

    def __init__(self, byte_range: Range, url: str, client):
        self.range = byte_range
        self.url = url
        self.client = client
        self.check_client()
        self.setup_stream()
        self.content_range = self.content_range_header()
        self._iterator = self.iter_raw()

    @property
    def range_header(self):
        return range_header(self.range)

    def setup_stream(self) -> None:
        """
        ``client.stream("GET", url)`` but leave the stream to be manually closed
        rather than using a context manager
        """
        self.request = self.client.build_request(
            method="GET", url=self.url, headers=self.range_header
        )
        self.response = self.client.send(request=self.request, stream=True)
        self.raise_for_non_partial_content()

    def raise_for_non_partial_content(self):
        """
        Raise the :class:`~range_streams.http_utils.PartialContentStatusError` if the response status code is
        anything other than 206 (Partial Content), as that is what was requested.
        """
        if self.response.status_code != 206:
            raise PartialContentStatusError(
                request=self.request, response=self.response
            )

    def content_range_header(self) -> str:
        """
        Validate request was range request by presence of ``content-range`` header
        """
        return detect_header_value(headers=self.response.headers, key="content-range")

    @property
    def total_content_length(self) -> int:
        """
        Obtain the total content length from the ``content-range`` header of a
        partial content HTTP GET request. This method is not used for the HTTP HEAD
        request sent when a :class:`~range_streams.range_stream.RangeStream` is
        initialised with an empty :class:`~ranges.Range` (since that is not a partial
        content request it returns a ``content-length`` header which can be read
        as an integer directly).
        """
        return int(self.content_range.split("/")[-1])

    def iter_raw(self) -> Iterator[bytes]:
        """
        Wrap the :meth:`iter_raw` method of the underlying :class:`httpx.Response`
        object within the :class:`~range_streams.range_response.RangeResponse` in
        :attr:`~range_streams.range_request.RangeRequest.response`.
        """
        return self.response.iter_raw()

    def close(self) -> None:
        """
        Close the :attr:`~range_streams.range_request.RangeRequest.response`
        :class:`~range_streams.range_response.RangeResponse`.
        """
        if not self.response.is_closed:
            self.response.close()

    def check_client(self):
        """
        Type checking workaround (Sphinx type hint extension does not like httpx
        so check the type manually with a method called at initialisation).
        """
        if not isinstance(self.client, httpx.Client):  # pragma: no cover
            raise NotImplementedError("Only HTTPX clients currently supported")
