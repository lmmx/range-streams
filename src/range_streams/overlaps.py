from __future__ import annotations

from typing import TYPE_CHECKING

from ranges import Range

from .range_utils import ext2int, most_recent_range, range_termini

if TYPE_CHECKING:  # pragma: no cover
    from ranges import RangeDict

    from range_streams import RangeStream

__all__ = ["handle_overlap", "overlap_whence"]


# This could be written more clearly by using a range_utils helper function shared with
# most_recent_range
def get_range_containing(rng_dict: RangeDict, position: int) -> Range:
    "Presumes range integrity has been checked, get a range by position it contains"
    # return next(k[0] for k, v in rng_dict.items() if position in k[0]).ranges()[0]
    rng_dict_kv = rng_dict.items()
    for k, _ in rng_dict_kv:
        if position in k[0]:
            rng = k[0].ranges()[0]
            return rng
    raise ValueError(f"No range containing position {position} in {rng_dict=}")


def burn_range(stream: RangeStream, overlapped_ext_rng: Range):
    internal_rng = ext2int(stream=stream, ext_rng=overlapped_ext_rng)
    stream._ranges.remove(internal_rng)
    # set `_active_range` to most recently registered internal range or None if empty
    stream._active_range = most_recent_range(stream, internal=True)


def handle_overlap(stream: RangeStream, rng: Range, internal: bool = False) -> None:
    """
    Handle overlaps with a given pruning level:

    0: "replant" ranges overlapped at the head with fresh, disjoint ranges 'downstream'
       or mark their tails to effectively truncate them if overlapped at the tail
    1: "burn" existing ranges overlapped anywhere by the new range
    2: "strict" will throw a ValueError
    """
    ranges = stream._ranges if internal else stream.ranges
    if stream.pruning_level not in range(3):
        raise ValueError("Pruning level must be 0, 1, or 2")
    # print(f"Handling {rng=} with {stream.pruning_level=}")
    if rng.isempty():
        raise ValueError("Range overlap not detected as the range is empty")
    if stream.pruning_level == 2:  # 2: strict
        raise ValueError("Range overlap not registered due to strict pruning policy")
    rng_min, rng_max = range_termini(rng)
    if rng not in ranges:
        # May be partially overlapping
        has_min, has_max = (pos in ranges for pos in [rng_min, rng_max])
        if has_min:
            # if has_min and has_max:
            #    print("Partially contained on multiple ranges")
            # T: Overlap at  tail   of pre-existing RangeResponse truncates that tail
            # M: Overlap at midbody of pre-existing RangeResponse truncates that tail
            overlapped_rng = get_range_containing(rng_dict=ranges, position=rng_min)
            # print(f"T/M {overlapped_rng=}")
            if stream.pruning_level == 1:  # 1: burn
                burn_range(stream=stream, overlapped_ext_rng=overlapped_rng)
            else:  # 0: replant
                o_rng_min, o_rng_max = range_termini(overlapped_rng)
                intersect_len = o_rng_max - rng_min + 1
                ranges[rng_min].tail_mark += intersect_len
        elif has_max:
            # H: Overlap at head of pre-existing RangeResponse is replanted or burnt
            overlapped_rng = get_range_containing(rng_dict=ranges, position=rng_max)
            # print(f"H {overlapped_rng=}")
            if stream.pruning_level == 1:  # 1: burn
                burn_range(stream=stream, overlapped_ext_rng=overlapped_rng)
            else:  # 0: replant
                o_rng_min, o_rng_max = range_termini(overlapped_rng)
                intersect_len = rng_max - o_rng_min + 1
                # For now, simply throw away: read `size=intersect_len` bytes of response,
                # consequently `tell` will trim the head computed in `ranges` property
                # _ = ranges[rng_max].read(intersect_len)
                burn_range(stream=stream, overlapped_ext_rng=overlapped_rng)
                if (new_o_rng_min := o_rng_min + intersect_len) > rng_max:
                    new_o_rng_max = o_rng_max  # (I can't think of exceptions to this?)
                    new_o_rng = Range(new_o_rng_min, new_o_rng_max + 1)
                    stream.add(new_o_rng)  # head-overlapped range has been 'replanted'
        else:
            info = f"{rng=} and {ranges=}"
            raise ValueError(f"Range overlap not detected at termini {info}")
    else:  # HTT: Full overlap with an existing range ("Head To Tail")
        overlapped_rng = get_range_containing(rng_dict=ranges, position=rng_max)
        # Fully overlapped ranges would be exhausted if read, so delete regardless of
        # whether pruning policy is "replant"/"burn" (i.e. can't replant empty range)
        # print(f"HTT {overlapped_rng=}")
        burn_range(stream=stream, overlapped_ext_rng=overlapped_rng)


def overlap_whence(
    stream: RangeStream, rng: Range, internal: bool = False
) -> int | None:
    """
    Determine if any overlap exists, whence (i.e. from where) on the pre-existing
    range it overlapped. 0 if the new range overlapped at the start ('head') of
    the existing range, 1 if fully contained (in the 'body'), 2 if at the end
    ('tail'), or None if the range is non-overlapping with any pre-existing range.

    Note: same convention as Python io module's SEEK_SET, SEEK_CUR, and SEEK_END.
    """
    ranges = stream._ranges if internal else stream.ranges
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
