from ranges import Range

__all__ = ["range_termini", "range_max"]


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


def range_min(r: Range) -> int:
    if r.isempty():
        raise ValueError("Empty range has no minimum")
    return range_termini(r)[0]


def range_max(r: Range) -> int:
    if r.isempty():
        raise ValueError("Empty range has no maximum")
    return range_termini(r)[1]
