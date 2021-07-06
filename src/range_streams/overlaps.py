from __future__ import annotations
from .range_utils import range_termini

from ranges import Range

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .range_stream import RangeStream

__all__ = ["handle_overlap"]


def handle_overlap(stream: RangeStream, rng: Range):
    if rng.isempty() or rng not in stream._ranges:
        raise ValueError("Range overlap not detected: check before calling handler")
    rng_min, rng_max = range_termini(rng)
    # Overlaps at the tail of a pre-existing RangeResponse erase the pre-existing tail

    # Overlaps at the head of a pre-existing RangeResponse are reduced and chained

    # Overlaps in the body of a pre-existing RangeResponse are treated equivalently to
    # overlaps at a pre-existing head ('head' is simply understood to be the earliest
    # unconsumed byte in the range).
