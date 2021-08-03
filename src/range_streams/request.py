from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

MYPY = False  # when using mypy will be overrided as True
if MYPY or not TYPE_CHECKING:  # pragma: no cover
    import httpx  # avoid importing to Sphinx type checker

from ranges import Range

from .http_utils import PartialContentStatusError, detect_header_value, range_header
from .range_utils import range_len

__all__ = ["RangeRequest"]


class RangeRequest:
    """
    Store a GET request and the response stream while keeping a reference to
    the client that spawned it, providing an overridable
    :attr:`~range_streams.response.RangeResponse._iterator` attribute
    [by default giving access to
    :meth:`~range_streams.response.RangeResponse.iter_raw`] on the
    underlying ``httpx.Response``, suitable for
    :class:`~range_streams.response.RangeResponse`
    to wrap in a :class:`io.BytesIO` buffered stream.
    """

    def __init__(
        self,
        byte_range: Range,
        url: str,
        client,
        GET_got: tuple | None = None,
        window_on_range: Range = Range(0, 0),
    ):
        """
        Make a new partial content request, or simulate one from a provided (completed)
        streaming GET request.

        The latter option should be used carefully to achieve improved performance from
        this library (in particular where read operations on the stream are expected to
        be linear, without large gaps between cursor positions which must be loaded
        prior to subsequent read operations).

        Args:
          byte_range      : The :class:`~ranges.Range` to request.
          url             : The URL to be requested.
          client          : The client to use for the request
          GET_got         : A 2-tuple of the already-executed ``httpx.Request``
                            and the received ``httpx.Response``, or ``None``
                            (the default). If provided, the ``byte_range`` is not
                            requested but instead is the range that was already
                            requested, and the ``url`` is the requested URL.
          window_on_range : If a non-empty range is passed, this is taken as the stream
                            this request is a window onto (indicating this is a
                            simulated request). Any read operations will be
                            restricted to this range of positions (as the underlying
                            stream being 'windowed' is a larger one).
        """
        self.range = byte_range
        self.url = url
        self.client = client
        self.check_client()
        # Allow a RangeRequest to be made from a pre-existing streamed GET request
        self.is_simulated = GET_got is not None
        self.window_on_range = window_on_range
        self.is_windowed = not window_on_range.isempty()
        if self.is_simulated:
            assert GET_got is not None  # give mypy a clue
            # "Simulating" a partial range request with pre-provided GET req. + response
            self.request, self.response = GET_got
            self._check_resp_req()  # Sphinx typing workaround
            # This shouldn't need to be accessed but set it to be thorough
            self.content_range = f"{self.range_header}/{range_len(byte_range)}"
            # self._iterator = None # must overwrite after initialisation
            self._iterator = None if self.is_windowed else self.iter_raw()
        else:
            # Make and send a partial range request
            self.setup_stream()
            self.content_range = self.content_range_header()
            self._iterator = self.iter_raw()

    @classmethod
    def windowed_request(
        cls,
        byte_range: Range,
        range_request: RangeRequest,
        tail_mark: int,
    ) -> RangeRequest:
        """
        Reuse the stream from an existing streaming request rather to create a new
        'windowed' RangeRequest from an existing RangeRequest, but change the byte range
        to be used on it. If the existing RangeRequest (``range_request``) is anything
        other than a stream of the full file range, then relative ranges will need to be
        calculated. This constructor was written on the assumption of a full file range.

        Args:
          byte_range : The :class:`~ranges.Range` provided by this request.
          on_request : The sent ``httpx.Request``
          tail_mark  : The :attr:`~range_streams.response.RangeResponse.tail_mark`
                       to trim the ``byte_range`` (if any). Passed separately
        """
        window_range = Range(byte_range.start, byte_range.end - tail_mark)
        # Build the request that this object pretends to have sent
        request_headers = range_header(window_range)
        unsent_request = range_request.client.build_request(
            method="GET",
            url=range_request.url,
            headers=request_headers,
        )
        content_byte_range = request_headers["range"].replace("=", " ")
        total_content_length = range_request.total_content_length
        window_on_range = range_request.range
        window_len = range_len(window_range)
        # Avoid having to import ``httpx.Response`` by calling ``type`` on one
        # HttpxResp_cls = type(range_request.response)
        # windowed_response = HttpxResp_cls(
        #    status_code=206,  # Partial Content
        #    headers={
        #        "accept-ranges": "bytes",
        #        "content-length": str(window_len),
        #        "content-range": f"{content_byte_range}/{total_content_length}",
        #    },
        #    stream=None, # do not consume the stream the window is being placed onto
        #    #stream=range_request.response.stream, # this consumes the parent's stream!
        #    request=unsent_request,
        # )
        # When iterating the stream via iter_raw, supply the source stream's iterator!
        # windowed_response.iter_raw = range_request.response.iter_raw
        windowed_response = range_request.response
        windowed_range_request = cls(
            byte_range=window_range,
            url=range_request.url,
            client=range_request.client,
            GET_got=(unsent_request, windowed_response),
            window_on_range=window_on_range,  # Keep a reference to the underlying range
        )
        # Calling ``response.iter_raw()`` again raises ``httpx.StreamConsumed`` error
        # so simply overwrite after initialisation with existing RangeRequest iterator
        windowed_range_request._iterator = range_request._iterator
        return windowed_range_request

    @classmethod
    def from_get_stream(cls, byte_range: Range, client, req, resp) -> RangeRequest:
        """
        Avoid making a new partial content request, instead interpret a streaming GET
        request as one when provided along with a ``byte_range``.

        Does not call
        :meth:`~range_streams.request.RangeRequest.raise_for_non_partial_content`
        as is done after setting the :attr:`~range_streams.request.RangeRequest.request`
        and :attr:`~range_streams.request.RangeRequest.response` in
        :meth:`~range_streams.request.RangeRequest.setup_stream`.

        Note: ``req`` and ``resp`` are type checked 'manually' at init (not via type
        hints) due to Sphinx type hints bug with the ``httpx`` library.

        Args:
          byte_range : The :class:`~ranges.Range` provided by this request.
          req        : The sent ``httpx.Request``
          resp       : The received ``httpx.Response``
        """
        range_request = cls(
            byte_range=byte_range,
            url=str(req.url),
            client=client,
            GET_got=(req, resp),
        )
        # range_request._iterator = resp.iter_raw()
        return range_request

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
        request sent when a :class:`~range_streams.stream.RangeStream` is
        initialised with an empty :class:`~ranges.Range` (since that is not a partial
        content request it returns a ``content-length`` header which can be read
        as an integer directly).
        """
        return int(self.content_range.split("/")[-1])

    def iter_raw(self) -> Iterator[bytes]:
        """
        Wrap the :meth:`iter_raw` method of the underlying :class:`httpx.Response`
        object within the :class:`~range_streams.response.RangeResponse` in
        :attr:`~range_streams.request.RangeRequest.response`.
        """
        return self.response.iter_raw()

    def close(self) -> None:
        """
        Close the :attr:`~range_streams.request.RangeRequest.response`
        :class:`~range_streams.response.RangeResponse`.
        """
        if not self.response.is_closed:
            self.response.close()

    def _check_resp_req(self):
        """
        Type checking workaround (Sphinx type hint extension does not like httpx
        so check the type manually with a method called at initialisation).
        """
        if not isinstance(self.request, httpx.Request):  # pragma: no cover
            raise NotImplementedError("Only HTTPX responses currently supported")
        if not isinstance(self.response, httpx.Response):  # pragma: no cover
            raise NotImplementedError("Only HTTPX responses currently supported")

    def check_client(self):
        """
        Type checking workaround (Sphinx type hint extension does not like httpx
        so check the type manually with a method called at initialisation).
        """
        if not any(
            isinstance(self.client, c) for c in (httpx.Client, httpx.AsyncClient)
        ):  # pragma: no cover
            raise NotImplementedError("Only HTTPX clients currently supported")
