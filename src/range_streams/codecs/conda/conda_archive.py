from __future__ import annotations

from ranges import Range

from ..zip import ZipStream

__all__ = ["CondaStream"]


class CondaStream(ZipStream):
    def __init__(
        self,
        url: str,
        client=None,
        byte_range: Range | tuple[int, int] = Range("[0, 0)"),
        pruning_level: int = 0,
    ):
        super().__init__(
            url=url, client=client, byte_range=byte_range, pruning_level=pruning_level
        )
