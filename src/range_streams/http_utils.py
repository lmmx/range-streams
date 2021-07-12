from __future__ import annotations

from ranges import Range

from .range_utils import range_termini

__all__ = ["byte_range_from_range_obj", "range_header"]


def byte_range_from_range_obj(rng: Range) -> str:
    if rng.isempty():
        byte_range = "-0"
    else:
        start_byte, end_byte = range_termini(rng)
        byte_range = f"{start_byte}-{end_byte}"
    return byte_range


def range_header(rng: Range) -> dict[str, str]:
    byte_range = byte_range_from_range_obj(rng)
    return {"range": f"bytes={byte_range}"}
