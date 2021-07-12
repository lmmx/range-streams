from __future__ import annotations

from typing import TYPE_CHECKING

from ranges import Range

from .range_utils import range_termini

if TYPE_CHECKING:
    from ranges import RangeDict  # pragma: no cover

__all__ = ["handle_overlap", "overlap_whence"]


def get_range_containing(rng_dict: RangeDict, position: int) -> Range:
    "Presumes range integrity has been checked, get a range by position it contains"
    # return next(k[0] for k, v in rng_dict.items() if position in k[0]).ranges()[0]
    rng_dict_kv = rng_dict.items()
    for k, _ in rng_dict_kv:
        if position in k[0]:
            rng = k[0].ranges()[0]
            return rng
    raise ValueError(f"No range containing position {position} in {rng_dict=}")


def handle_overlap(stream: RangeStream, rng: Range, internal: bool = False) -> None:
    ranges = stream._ranges if internal else stream.ranges
    if rng.isempty():
        raise ValueError("Range overlap not detected as the range is empty")
    rng_min, rng_max = range_termini(rng)
    if rng not in ranges:
        # May be partially overlapping
        has_min, has_max = (pos in ranges for pos in [rng_min, rng_max])
        if has_min and has_max:
            raise NotImplementedError("Partially contained on multiple ranges")
        if has_min:
            # Overlap at tail of pre-existing RangeResponse erases pre-existing tail
            overlapped_rng = get_range_containing(rng_dict=ranges, position=rng_min)
            o_rng_min, o_rng_max = range_termini(overlapped_rng)
            intersect_len = o_rng_max - rng_min + 1
            ranges[rng_min].tail_mark += intersect_len
        elif has_max:
            # Overlap at head of pre-existing RangeResponse is reduced and chained
            overlapped_rng = get_range_containing(rng_dict=ranges, position=rng_max)
            o_rng_min, o_rng_max = range_termini(overlapped_rng)
            intersect_len = o_rng_max - rng_min + 1
            # TODO: Slice the iterator for the pre-existing range by `intersect_len`
            # bytes, chain the 1st slice onto the end of the iterator of the
            # response created, the 2nd slice will go back as the shortened range?
            # For now, simply throw away: read `size=intersect_len` bytes of response,
            # consequently `tell` will trim the head computed in `ranges` property
            _ = ranges[rng_max].read(intersect_len)
        else:
            info = f"{rng=} and {ranges=}"
            raise ValueError(f"Range overlap not detected at termini {info}")
    else:  # Full overlap with an existing range
        # Overlaps in body of a pre-existing RangeResponse are treated equivalently
        # to overlaps at a pre-existing head ('head' is simply understood to be
        # the earliest unconsumed byte in the range). The only difference is here
        # the 'preamble' must be read in from the head before reaching the overlap
        overlapped_rng = get_range_containing(rng_dict=ranges, position=rng_max)
        o_rng_min, o_rng_max = range_termini(overlapped_rng)
        preamble_len = rng_min - o_rng_min + 1
        intersect_len = o_rng_max - rng_min + 1
        # TODO: Slice the iterator for the pre-existing range by
        # `preamble_len + intersect_len` bytes, chain the 1st slice onto the end
        # of the iterator of the response created, the 2nd slice will go back as
        # the shortened range? For now, simply throw away: read
        # `size=preamble_len + intersect_len` bytes of response, consequently
        # `tell` will trim the head computed in `ranges` property
        _ = ranges[rng_max].read(preamble_len + intersect_len)


def overlap_whence(ranges: RangeDict, rng: Range) -> int | None:
    """
    Determine if any overlap exists, whence (i.e. from where) on the pre-existing
    range it overlapped. 0 if the new range overlapped at the start ('head') of
    the existing range, 1 if fully contained (in the 'body'), 2 if at the end
    ('tail'), or None if the range is non-overlapping with any pre-existing range.

    Note: same convention as Python io module's SEEK_SET, SEEK_CUR, and SEEK_END.
    """
    if rng in ranges:
        # Full overlap (i.e. in middle of pre-existing range)
        whence = 1  # type: int | None
    else:
        # If minimum (max.) terminus overlaps a range, it's a tail (head) overlap
        tail_over, head_over = [t in ranges for t in range_termini(rng)]
        if tail_over:
            whence = 2
        elif head_over:
            whence = 0
        else:
            whence = None
    return whence
