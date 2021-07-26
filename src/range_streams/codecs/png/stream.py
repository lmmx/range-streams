from __future__ import annotations

import struct

from ranges import Range

from ...range_stream import RangeStream
from .data import PngData

__all__ = ["PngStream"]


class PngStream(RangeStream):
    def __init__(
        self,
        url: str,
        client=None,
        byte_range: Range | tuple[int, int] = Range("[0, 0)"),
        pruning_level: int = 0,
        scan_header: bool = True,
    ):
        """
        As for RangeStream, but if `scan_header` is True, then immediately call
        :meth:`check_header_rec` on initialisation (which will perform a series
        of range requests to read the PNG metadata from the header record), setting
        :attr:`metadata`.
        Setting this can be postponed until first access of the :attr:`metadata`
        property.
        """
        super().__init__(
            url=url, client=client, byte_range=byte_range, pruning_level=pruning_level
        )
        self.data = PngData()
        if scan_header:
            self.scan_ihdr()

    def scan_ihdr(self):
        ihdr_rng = Range(self.data.IHDR.start_pos, self.data.IHDR.end_pos)
        self.add(ihdr_rng)
        ihdr_bytes = self.active_range_response.read()
        ihdr_u = struct.unpack(self.data.IHDR.struct, ihdr_bytes)
        self.data.IHDR.width = ihdr_u[self.data.IHDR.parts._IHDR_WIDTH]
        self.data.IHDR.height = ihdr_u[self.data.IHDR.parts._IHDR_HEIGHT]
        self.data.IHDR.bit_depth = ihdr_u[self.data.IHDR.parts._IHDR_BIT_DEPTH]
        self.data.IHDR.colour_type = ihdr_u[self.data.IHDR.parts._IHDR_COLOUR_TYPE]
        self.data.IHDR.compression = ihdr_u[self.data.IHDR.parts._IHDR_COMPRESSION]
        self.data.IHDR.filter_method = ihdr_u[self.data.IHDR.parts._IHDR_FILTER_METHOD]
        self.data.IHDR.interlacing = ihdr_u[self.data.IHDR.parts._IHDR_INTERLACING]
