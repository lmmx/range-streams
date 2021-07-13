from __future__ import annotations

from ranges import Range

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

if TYPE_CHECKING:  # pragma: no cover
    from ranges import RangeDict

    from .range_response import RangeResponse
    from .range_stream import RangeStream


def ranges_in_reg_order(ranges: RangeDict) -> list[Range]:
    "Presumes integrity is already checked: ranges in order of registration"
    return [k[0].ranges()[0] for k, v in ranges.items()]


def response_ranges_in_reg_order(ranges: RangeDict) -> list[Range]:
    "RangeResponse requested ranges in order of registration"
    return [v.request.range for k, v in ranges.items()]


def most_recent_range(stream: RangeStream, internal: bool = True) -> Range | None:
    if stream._ranges.isempty():
        rng = None  # type: Range | None
    else:
        ranges = stream._ranges if internal else stream.ranges
        rng = ranges_in_reg_order(ranges)[-1]
    return rng


def range_termini(rng: Range) -> tuple[int, int]:
    """
    Get the inclusive start and end positions `[start,end]` from a `ranges.Range`.
    These are referred to as the 'termini'. Ranges are always ascending.
    """
    if rng.isempty():
        raise ValueError("Empty range has no termini")
    # If range is not empty then can compare regardless of if interval is closed/open
    start = rng.start if rng.include_start else rng.start + 1
    end = rng.end if rng.include_end else rng.end - 1
    return start, end


def range_len(rng: Range) -> int:
    rmin, rmax = range_termini(rng)
    return rmax - rmin


def range_min(rng: Range) -> int:
    if rng.isempty():
        raise ValueError("Empty range has no minimum")
    return range_termini(rng)[0]


def range_max(rng: Range) -> int:
    if rng.isempty():
        raise ValueError("Empty range has no maximum")
    return range_termini(rng)[1]


def validate_range(
    byte_range: Range | tuple[int, int], allow_empty: bool = True
) -> Range:
    "Validate byte_range and convert to `[a,b)` Range if given as integer tuple"
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
    """
    Assumes input list of RangeSets are in ascending order, switches if not
    """
    first_termini = range_termini(ranges[0])
    last_termini = range_termini(ranges[-1])
    if first_termini > last_termini:
        first_termini, last_termini = last_termini, first_termini
    min_start, _ = first_termini
    _, max_end = last_termini
    return Range(min_start, max_end + 1)


def ext2int(stream: RangeStream, ext_rng: Range) -> RangeResponse:
    """
    Given the external range `ext_rng` and the RangeStream `stream` on which it is
    'stored' (or rather, computed, in the `ranges` property), return the internal
    Range stored on the `_ranges` attribute of the RangeStream, by looking up the
    shared `RangeResponse` value.
    """
    rng_response = stream.ranges[ext_rng]
    for k, v in stream._ranges.items():
        if v == rng_response:
            return k[0].ranges()[0]
    raise ValueError("Looked up a non-existent key in the internal RangeDict")
