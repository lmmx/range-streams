from __future__ import annotations

__all__ = [
    "range_termini",
    "range_min",
    "range_max",
    "validate_range",
    "range_span",
    "range_len",
    "ext2int",
]

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ranges
from ranges import Range, RangeDict

import range_streams


def ranges_in_reg_order(ranges: RangeDict) -> list[Range]:
    """Given a :class:`~ranges.RangeDict`,
    list the ranges in order of registration.
    
    Presumes integrity is already checked.
    
    Args:
      ranges : Either the internal or external ranges of a
               :class:`~range_streams.range_stream.RangeStream`.
    """
    return [k[0].ranges()[0] for k, v in ranges.items()]


def response_ranges_in_reg_order(ranges: RangeDict) -> list[Range]:
    """For all of the :class:~range_streams.range_response.RangeResponse`
    values in the :class:`ranges.RangeDict`, list the ranges from their
    original :attribute:~range_streams.range_response.RangeResponse.request`
    in order of registration.
    
    Args:
      ranges : Either the internal or external ranges of a
               :class:`~range_streams.range_stream.RangeStream`.
    """
    return [v.request.range for k, v in ranges.items()]


def most_recent_range(
    stream: range_streams.range_stream.RangeStream, internal: bool = True
) -> Range | None:
    """For all of the :class:`~range_streams.range_response.RangeResponse`
    values in the :class:`ranges.RangeDict`, list the ranges from their
    original :attr:`~range_streams.range_response.RangeResponse.request`
    in order of registration.
    
    If ``internal`` is ``True``, use
    :attr:`~range_streams.range_stream.RangeStream._ranges` as the
    :class:`ranges.RangeDict`, else use the 'external' (computed) property
    :attr:`~range_streams.range_stream.RangeStream.ranges`. The external
    ones take into account the position the file has been read/seeked to.
    
    Args:
      stream   : Either the internal or external ranges of a
                 :class:`~range_streams.range_stream.RangeStream`.
      internal : Whether to use the internal or external ranges.
    """
    if stream._ranges.isempty():
        rng = None  # type: Range | None
    else:
        ranges = stream._ranges if internal else stream.ranges
        rng = ranges_in_reg_order(ranges)[-1]
    return rng


def range_termini(rng: Range) -> tuple[int, int]:
    """Get the inclusive start and end positions ``[start,end]``
    from a :class`ranges.Range`. These are referred to as the
    'termini'. Ranges are always ascending.
    
    Args:
      rng : A :class:`~ranges.Range` (which by default will be
            half-closed, i.e. not inclusive of the end position).
    """
    if rng.isempty():
        raise ValueError("Empty range has no termini")
    # If range is not empty then can compare regardless of if interval is closed/open
    start = rng.start if rng.include_start else rng.start + 1
    end = rng.end if rng.include_end else rng.end - 1
    return start, end


def range_len(rng: Range) -> int:
    """Get the length of a :class:`~ranges.Range`.
    
    Args:
      rng : A :class:`~ranges.Range` (which by default will be
            half-closed, i.e. not inclusive of the end position).
    """
    rmin, rmax = range_termini(rng)
    return rmax - rmin


def range_min(rng: Range) -> int:
    """Get the minimum (or start terminus) of a :class:`~ranges.Range`.
    
    Args:
      rng : A :class:`~ranges.Range` (which by default will be
            half-closed, i.e. not inclusive of the end position).
    """
    if rng.isempty():
        raise ValueError("Empty range has no minimum")
    return range_termini(rng)[0]


def range_max(rng: Range) -> int:
    """Get the maximum (or end terminus) of a :class:`~ranges.Range`.
    
    Args:
      rng : A :class:`~ranges.Range` (which by default will be
            half-closed, i.e. not inclusive of the end position).
    """
    if rng.isempty():
        raise ValueError("Empty range has no maximum")
    return range_termini(rng)[1]


def validate_range(
    byte_range: Range | tuple[int, int], allow_empty: bool = True
) -> Range:
    """Validate ``byte_range`` and convert to a half-closed (i.e.
    not inclusive of the end position) ``[start,end)`` :class:`ranges.Range`
    if given as integer tuple.
    
    Args:
      byte_range : Either a :class:`tuple` of two :class:`int` positions with
                   which to create a :class:`~ranges.Range` (which by
                   default will be half-closed, i.e. not inclusive of
                   the end position); or simply a :class:`~ranges.Range`.
    """
    complain_about_types = (
        f"{byte_range=} must be a Range from the python-ranges"
        " package or an integer 2-tuple"
    )
    if isinstance(byte_range, tuple):
        if not all(map(lambda x: isinstance(x, int), byte_range)):
            raise TypeError(complain_about_types)
        if len(byte_range) != 2:
            raise TypeError(complain_about_types)
        byte_range = Range(*byte_range)
    elif not isinstance(byte_range, Range):
        raise TypeError(complain_about_types)
    elif not all(map(lambda o: isinstance(o, int), [byte_range.start, byte_range.end])):
        raise TypeError("Ranges must be discrete: use integers for start and end")
    if not allow_empty and byte_range.isempty():
        raise ValueError("Range is empty")
    return byte_range


def range_span(ranges: list[Range]) -> Range:
    """Given a list of :class:`~ranges.Range`, calculate their 'span'
    (i.e. the range spanned from their minimum to maximum). This span
    may of course not be completely 'covered' by the ranges in the list.
    
    Assumes input list of :class:`RangeSets` are in ascending order,
    switches if not.
    
    Args:
      ranges : A list of ranges whose span is to be given.
    """
    first_termini = range_termini(ranges[0])
    last_termini = range_termini(ranges[-1])
    if first_termini > last_termini:
        first_termini, last_termini = last_termini, first_termini
    min_start, _ = first_termini
    _, max_end = last_termini
    return Range(min_start, max_end + 1)


def ext2int(
    stream: range_streams.range_stream.RangeStream, ext_rng: Range
) -> range_streams.range_stream.RangeResponse:
    """Given the external range `ext_rng` and the :class:`RangeStream`
    ``stream`` on which it is 'stored' (or rather, computed, in the
    :attr:`~range_streams.range_stream.RangeStream.ranges` property),
    return the internal :class:`~ranges.Range` stored on the
    :attr:`_ranges` attribute of the
    :attr:`~range_streams.range_stream.RangeStream`, by looking up the
    shared :class:`RangeResponse` value.
    
    Args:
      stream  : A :class:`~range_streams.range_stream.RangeStream`
                in whose 'external'
                :attr:`~range_streams.range_stream.RangeStream.ranges`
                property :class:`ranges.RangeDict` the ``ext_rng`` is
                found.
      ext_rng : A :class:`ranges.Range` from the 'external'
                :attr:`~range_streams.range_stream.RangeStream.ranges`
                with which to cross-reference in
                :attr:`~range_streams.range_stream.RangeStream._ranges`
                to identify the corresponding 'internal' range.
    """
    rng_response = stream.ranges[ext_rng]
    for k, v in stream._ranges.items():
        if v == rng_response:
            return k[0].ranges()[0]
    raise ValueError("Looked up a non-existent key in the internal RangeDict")
