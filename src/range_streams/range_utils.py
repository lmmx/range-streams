from __future__ import annotations

from ranges import Range

__all__ = [
    "range_termini",
    "range_min",
    "range_max",
    "validate_range",
    "range_span",
    "range_len",
]


def range_termini(r: Range) -> tuple[int, int]:
    """
    Get the inclusive start and end positions `[start,end]` from a `ranges.Range`.
    These are referred to as the 'termini'. Ranges are always ascending.
    """
    if r.isempty():
        raise ValueError("Empty range has no termini")
    # If range is not empty then can compare regardless of if interval is closed/open
    start = r.start if r.include_start else r.start + 1
    end = r.end if r.include_end else r.end - 1
    return start, end


def range_len(rng: Range) -> int:
    rmin, rmax = range_termini(rng)
    return rmax - rmin


def range_min(r: Range) -> int:
    if r.isempty():
        raise ValueError("Empty range has no minimum")
    return range_termini(r)[0]


def range_max(r: Range) -> int:
    if r.isempty():
        raise ValueError("Empty range has no maximum")
    return range_termini(r)[1]


def validate_range(
    byte_range: Range | tuple[int, int], allow_empty: bool = True
) -> Range:
    "Validate byte_range and convert to `[a,b)` Range if given as integer tuple"
    complain_about_types = (
        f"{byte_range=} must be a `Range` from the `python-ranges`"
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
        raise TypeError("Ranges must be discrete (use integers for start and end)")
    if not allow_empty and byte_range.isempty():
        raise TypeError("Range is empty")
    return byte_range


def range_span(ranges: list[Range]) -> Range:
    "Assumes input list of RangeSets are in ascending order"
    min_start, _ = range_termini(ranges[0])
    _, max_end = range_termini(ranges[-1])
    return Range(min_start, max_end + 1)
