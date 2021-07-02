from __future__ import annotations
import httpx
from ranges import Range

__all__ = ["request_range"]

def byte_range_from_range_obj(target_range: Range) -> str:
    if range.isempty():
        byte_range = "-0"
    else:
        start_byte = target_range.start
        end_byte = target_range.end
        # range request byte range is both start-/end-inclusive
        if not target_range.include_start:
            start_byte += 1 # avoid false start
        if not target_range.include_end:
            end_byte -= 1
        byte_range = f"{start_byte}-{end_byte}"
    return byte_range


def range_header(target_range: Range) -> dict[str,str]:
    byte_range = byte_range_from_range_obj(target_range)
    return {"range": f"bytes={byte_range}"}


# Returns `httpx.Response | requests.Response` (or whichever library used)
def request_range(url: str, target_range: Range, client, headers: dict | None = None):
    rh = range_header(target_range)
    headers = {**headers, **rh} if headers is not None else rh
    return client.get(url, headers=headers)
