from __future__ import annotations

from typing import TypeVar

import range_streams

all__ = ["_T"]

_T = TypeVar(
    "_T", bound="range_streams.stream.RangeStream"
)  # RangeStream or a subclass
