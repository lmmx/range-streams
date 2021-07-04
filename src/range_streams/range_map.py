from __future__ import annotations
from ranges import Range, RangeSet, RangeDict

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .range_stream import RangeStream

class RangeMap(RangeDict):
    """
    A RangeDict associated with a parent RangeStream, used to keep track of the
    ranges requested from a stream (RangeDict Range keys) and their state (values:
    RangeState?).
    """
    def __init__(self, parent_stream: RangeStream):
        self._parent_stream = parent_stream

    def __repr__(self):
        super().__repr__(self)

    def register_range(self, rng: Range):
        self.add(new_range, None)
