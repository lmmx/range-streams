r"""When preparing a HTTP GET request, the HTTP `range request
<https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests>`_
header must be provided as a :class:`dict`, for example:

.. code-block:: python

    {"range": "bytes=0-1"}

would request the two bytes at positions ``0`` and ``1`` (i.e. the inclusive
interval ``[0,1]``).

An empty range can also be specified with the value ``bytes="-0"``, which is useful to
determine the total length of a file (as the `Content-Range
<https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Range>`_ header
returned by the server contains the total size of the file from which the range was taken).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ranges import Range

if TYPE_CHECKING:  # pragma: no cover
    import ranges  # for sphinx

from .range_utils import range_termini

__all__ = ["byte_range_from_range_obj", "range_header"]


def byte_range_from_range_obj(rng: Range) -> str:
    """Prepare the byte range substring for a HTTP `range request
    <https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests>`_.

    For example:

      >>> from range_streams.http_utils import byte_range_from_range_obj
      >>> byte_range_from_range_obj(Range(0,2))
      '0-1'

    Args:
      rng : range of the bytes to be requested (0-based)

    Returns:
      A hyphen-separated string of start and end positions. The start position
      is missing if the range provided is empty, and this corresponds to a request
      for "the last zero bytes" i.e. an empty range request.
    """
    if rng.isempty():
        byte_range = "-0"
    else:
        start_byte, end_byte = range_termini(rng)
        byte_range = f"{start_byte}-{end_byte}"
    return byte_range


def range_header(rng: Range) -> dict[str, str]:
    """Prepare a :class:`dict` to pass as a :mod:`httpx` request header
    with a single key ``ranges`` whose value is the byte range.

    For example:

      >>> from range_streams.http_utils import range_header
      >>> range_header(Range(0,2))
      {'range': 'bytes=0-1'}

    Args:
      rng : range of the bytes to be requested (0-based)

    Returns:
      :class:`dict` suitable to be passed to :meth:`httpx.Client.build_request`
      in :meth:`~range_streams.range_request.RangeRequest.setup_stream` through :attr:`~range_streams.range_request.RangeRequest.range_header`
    """
    byte_range = byte_range_from_range_obj(rng)
    return {"range": f"bytes={byte_range}"}
