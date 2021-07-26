from __future__ import annotations

import struct

from ranges import Range

from ...range_stream import RangeStream
from .data import PngChunkInfo, PngData

__all__ = ["PngStream"]


class PngStream(RangeStream):
    def __init__(
        self,
        url: str,
        client=None,
        byte_range: Range | tuple[int, int] = Range("[0, 0)"),
        pruning_level: int = 0,
        scan_ihdr: bool = True,
        enumerate_chunks: bool = True,
    ):
        """
        As for RangeStream, but if `scan_ihdr` is True, then immediately call
        :meth:`~PngStream.scan_ihdr` on initialisation (which will perform the
        necessary range request to read PNG metadata from its IHDR chunk), setting
        various attributes on the :attr:`PngStream.data.IHDR` object.

        Populating these attributes can be postponed [until manually calling
        :meth:`PngStream.scan_ihdr` and :meth:`PngStream.enumerate_chunks`]
        to avoid sending any range requests at initialisation.
        """
        super().__init__(
            url=url, client=client, byte_range=byte_range, pruning_level=pruning_level
        )
        self.data = PngData()
        if scan_ihdr:
            self.scan_ihdr()
        if enumerate_chunks:
            self.chunks: dict[str, list[PngChunkInfo]] = self.enumerate_chunks()

    def scan_ihdr(self):
        """
        Request a range on the stream corresponding to the IHDR chunk, and populate
        the :attr:`PngStream.data.IHDR` object (an instance of :class:`IHDRChunk`
        from the :mod:`range_streams.codecs.png.data` module) according to the spec.
        """
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

    def enumerate_chunks(self):
        """
        Parse the length and type chunks, then skip past the chunk data and CRC chunk,
        so as to enumerate all chunks in the PNG (but request and read as little as
        possible). Build a dictionary of all chunks with keys of the chunk type (four
        letter strings) and values of lists (since some chunks e.g. IDAT can appear
        multiple times in the PNG).
        """
        png_signature = 8  # PNG files start with an 8-byte signature
        chunk_preamble_size = 8  # 4-byte length chunk + 4-byte type chunk
        chunks: dict[str, list[PngChunkInfo]] = {}
        chunk_start = png_signature  # Skip PNG file signature to reach first chunk
        chunk_type: str | None = None  # initialise for while loop condition
        while chunk_type != "IEND":
            if chunks:
                # Increment chunk_start from last iteration
                # (last chunk's end is this chunk's start)
                chunk_start = chunk_info.end  # type: ignore
            chunk_length_rng = Range(chunk_start, chunk_start + chunk_preamble_size)
            self.add(chunk_length_rng)
            b = self.active_range_response.read()
            chunk_len = struct.unpack(">I", b[:4])[0]
            chunk_type = b[4:].decode("ascii")
            assert chunk_type is not None  # appease mypy
            chunks.setdefault(chunk_type, [])
            chunk_info = PngChunkInfo(
                start=chunk_start, type=chunk_type, length=chunk_len
            )
            chunks[chunk_type].append(chunk_info)
        return chunks
