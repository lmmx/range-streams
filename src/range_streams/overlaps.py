from __future__ import annotations

from typing import TYPE_CHECKING

from .range_utils import range_termini

if TYPE_CHECKING:  # pragma: no cover
    from ranges import Range, RangeDict


__all__ = ["get_range_containing", "overlap_whence"]

# This could be written more clearly by using a range_utils helper function shared with
# most_recent_range
def get_range_containing(rng_dict: RangeDict, position: int) -> Range:
    """Get a :class:`~ranges.Range` from ``rng_dict`` by looking up the ``position`` it
    contains, where ``rng_dict`` is either the internal
    :obj:`RangeStream._ranges` attribute
    or the external :obj:`~range_streams.stream.RangeStream.ranges` property.

    Presumes range integrity has been checked.

    Raises :exc:`ValueError` if ``position`` is not in ``rng_dict``.

    Args:
      rng_dict : input range
      position : the position at which to look up
    """
    # return next(k[0] for k, v in rng_dict.items() if position in k[0]).ranges()[0]
    rng_dict_kv = rng_dict.items()
    for k, _ in rng_dict_kv:
        if position in k[0]:
            rng = k[0].ranges()[0]
            return rng
    raise ValueError(f"No range containing position {position} in {rng_dict=}")


def overlap_whence(
    rng_dict: RangeDict,
    rng: Range,
) -> int | None:
    """
    Determine if any overlap exists, whence (i.e. from where) on the pre-existing
    range it overlapped. ``0`` if the new range overlapped at the start ('head') of
    the existing range, ``1`` if fully contained (in the 'body'), ``2`` if at the end
    ('tail'), or ``None`` if the range is non-overlapping with any pre-existing range.

    Note: same convention as Python io module's
    :obj:`~io.SEEK_SET`, :obj:`~io.SEEK_CUR`, and :obj:`~io.SEEK_END`.
    """
    if rng in rng_dict:
        # Full overlap (i.e. in middle of pre-existing range)
        whence = 1  # type: int | None
    else:
        # If minimum (max.) terminus overlaps a range, it's a tail (head) overlap
        tail_over, head_over = [t in rng_dict for t in range_termini(rng)]
        if tail_over:
            whence = 2
        elif head_over:
            whence = 0
        else:
            whence = None
    return whence
