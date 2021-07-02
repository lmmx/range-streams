from __future__ import annotations
from ranges import Range
from .range_utils import range_termini

__all__ = ["request_range"]

def byte_range_from_range_obj(r: Range) -> str:
    if r.isempty():
        byte_range = "-0"
    else:
        start_byte, end_byte = range_termini(r)
        byte_range = f"{start_byte}-{end_byte}"
    return byte_range


def range_header(r: Range) -> dict[str,str]:
    byte_range = byte_range_from_range_obj(r)
    return {"range": f"bytes={byte_range}"}


# Returns `httpx.Response | requests.Response` (or whichever library used)
def request_range(url: str, r: Range, client, headers: dict | None = None):
    rh = range_header(r)
    headers = {**headers, **rh} if headers is not None else rh
    return client.get(url, headers=headers)
