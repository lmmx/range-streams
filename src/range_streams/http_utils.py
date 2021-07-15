from __future__ import annotations

from typing import TYPE_CHECKING

from ranges import Range

if TYPE_CHECKING:
    import ranges

from .range_utils import range_termini

__all__ = ["byte_range_from_range_obj", "range_header"]


def byte_range_from_range_obj(rng: Range) -> str:
    """Prepare the byte range substring for a HTTP `range request
    <https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests>`_.

    Args:
      rng : range of the bytes to be requested (0-based)
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

    Args:
      rng : range of the bytes to be requested (0-based)
    """
    byte_range = byte_range_from_range_obj(rng)
    return {"range": f"bytes={byte_range}"}
