from __future__ import annotations

import struct
import zlib

from ranges import Range

from ...stream import RangeStream
from .data import PngChunkInfo, PngData
from .reconstruct import reconstruct_idat

__all__ = ["PngStream"]


class PngStream(RangeStream):
    """
    As for RangeStream, but if `scan_ihdr` is True, then immediately call
    :meth:`~range_streams.codecs.png.PngStream.scan_ihdr` on initialisation
    (which will perform the necessary range request to read PNG metadata
    from its IHDR chunk), setting various attributes on the
    :attr:`~range_streams.codecs.png.PngStream.data.IHDR` object.

    Populating these attributes can be postponed [until manually calling
    :meth:`~range_streams.codecs.png.PngStream.scan_ihdr` and
    :meth:`~range_streams.codecs.png.PngStream.enumerate_chunks`]
    to avoid sending any range requests at initialisation.
    """

    def __init__(
        self,
        url: str,
        client=None,
        byte_range: Range | tuple[int, int] = Range("[0, 0)"),
        pruning_level: int = 0,
        single_request: bool = True,
        scan_ihdr: bool = True,
        enumerate_chunks: bool = True,
        chunk_size: int | None = None,
    ):
        """
        Set up a stream for the PNG file at ``url``, with either an initial range to be
        requested (HTTP partial content request), or if left as the empty range
        (default: ``Range(0,0)``) a HEAD request will be sent instead, so as to set the
        total size of the target file on the
        :attr:`~range_streams.stream.RangeStream.total_bytes` property.

        By default (if ``client`` is left as ``None``) a fresh :class:`httpx.Client`
        will be created for each stream.

        The ``byte_range`` can be specified as either a :class:`~ranges.Range` object,
        or 2-tuple of integers (``(start, end)``), interpreted either way as a
        half-closed interval ``[start, end)``, as given by Python's built-in
        :class:`range`.

        The ``pruning_level`` controls the policy for overlap handling (``0`` will
        resize overlapped ranges, ``1`` will delete overlapped ranges, and ``2`` will
        raise an error when a new range is added which overlaps a pre-existing range).

        If ``single_request`` is ``True`` (default: ``True``), then the behaviour when
        an empty ``byte_range`` is passed instead becomes to send a standard streaming
        GET request (not a partial content request at all), and instead the class will
        then facilitate an interface that 'simulates' these calls, i.e. as if each time
        :meth:`~range_streams.stream.RangeStream.add` was used the range requests were
        being returned instantly (as everything needed was already obtained on the first
        request at initialisation). More performant when reading a stream linearly,
        and defaults to ``True`` in the PNG codec as chunks are read linearly.

        - See docs for the
          :meth:`~range_streams.stream.RangeStream.handle_overlap`
          method for further details.

        Args:
          url              : (:class:`str`) The URL of the file to be streamed
          client           : (:class:`httpx.Client` | ``None``) The HTTPX client
                             to use for HTTP requests
          byte_range       : (:class:`~ranges.Range` | ``tuple[int,int]``) The range
                             of positions on the file to be requested
          pruning_level    : (:class:`int`) Either ``0`` ('replant'), ``1`` ('burn'),
                             or ``2`` ('strict')
          single_request   : (:class:`bool`) Whether to use a single GET request and
                             just add 'windows' onto this rather than create multiple
                             partial content requests.
          scan_ihdr        : (:class:`bool`) Whether to scan the IHDR chunk on
                             initialisation
          enumerate_chunks : (:class:`bool`) Whether to step through each chunk
                             (read its metadata, and proceed until all chunks have
                             been identified) upon initialisation
          chunk_size       : (:class:`int` | ``None``) The chunk size used for the
                             ``httpx.Response.iter_raw`` response byte iterators
        """
        super().__init__(
            url=url,
            client=client,
            byte_range=byte_range,
            pruning_level=pruning_level,
            single_request=single_request,
        )
        if enumerate_chunks:
            self.populate_chunks()
        self.data = PngData()
        if scan_ihdr:
            self.scan_ihdr()

    def populate_chunks(self):
        """
        Call :meth:`~range_streams.codecs.png.PngStream.enumerate_chunks`
        and store in the internal
        :attr:`~range_streams.codecs.png.PngStream._chunks` attribute,
        accessible through the :attr:`~range_streams.codecs.png.PngStream.chunks`
        property.

        If the :attr:`~range_streams.codecs.png.PngStream.chunks` property is
        called 'prematurely', to avoid an access error it will 'proactively'
        call this method before returning the gated internal attribute.
        """
        self._chunks: dict[str, list[PngChunkInfo]] = self.enumerate_chunks()

    @property
    def chunks(self):
        """
        'Gate' to the internal :attr:`~range_streams.codecs.png.PngStream._chunks`
        attribute.

        If this property is called before the internal attribute is set,
        ('prematurely'), to avoid an access error it will 'proactively'
        call :meth:`~range_streams.codecs.png.PngStream.populate_chunks`
        before returning the gated internal attribute.
        """
        if not hasattr(self, "_chunks"):
            self.populate_chunks()
        return self._chunks

    def scan_ihdr(self):
        """
        Request a range on the stream corresponding to the IHDR chunk, and populate
        the :attr:`~range_streams.codecs.png.PngStream.data.IHDR` object (an instance
        of :class:`IHDRChunk` from the :mod:`range_streams.codecs.png.data` module)
        according to the spec.
        """
        ihdr_rng = Range(self.data.IHDR.start_pos, self.data.IHDR.end_pos)
        self.add(ihdr_rng)
        ihdr_bytes = self.active_range_response.read()
        ihdr_u = struct.unpack(self.data.IHDR.struct, ihdr_bytes)
        if None in ihdr_u:
            raise ValueError(f"Got a null from unpacking IHDR bytes {ihdr_u}")
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

        See `the official specification
        <http://www.libpng.org/pub/png/spec/1.2/PNG-Chunks.html>`_ for full details
        (or `Wikipedia
        <https://en.wikipedia.org/wiki/
        Portable_Network_Graphics#%22Chunks%22_within_the_file>`_,
        or `the W3C <https://www.w3.org/TR/PNG/#5Chunk-layout>`_).
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

    def get_chunk_data(self, chunk_info: PngChunkInfo) -> bytes:
        self.add(chunk_info.data_range)
        b = self.active_range_response.read()
        return b

    def get_idat_data(self) -> list[int]:
        """
        Decompress the IDAT chunk(s) and concatenate, then confirm the length is
        exactly equal to ``height * (1 + width * bit_depth)``, and filter it
        (removing the filter byte at the start of each scanline) using
        :func:`reconstruct_idat`.
        """
        if self.data.IHDR.colour_type is None:
            self.scan_ihdr()
        height = self.data.IHDR.height
        width = self.data.IHDR.width
        channels = self.data.IHDR.channel_count
        assert height is not None and width is not None and channels is not None
        expected_length = height * (1 + width * channels)
        b = zlib.decompress(
            b"".join(
                self.get_chunk_data(chunk_info) for chunk_info in self.chunks["IDAT"]
            )
        )
        if len(b) != expected_length:
            raise ValueError(f"Expected {expected_length} but got {len(b)}")
        return reconstruct_idat(
            idat_bytes=b, channels=channels, height=height, width=width
        )

    def has_chunk(self, chunk_type: str) -> bool:
        """
        Determine whether the given chunk type is one of the chunks defined in the PNG.
        If the chunks have not yet been parsed, they will first be enumerated.
        """
        return chunk_type in self.chunks

    @property
    def alpha_as_direct(self):
        """
        To avoid distinguishing 'direct' image transparency (in IDAT) from
        'indirect' (or computed, from tRNS) palette transparency, check for
        a colour map and then check for a tRNS chunk to determine overall
        whether this image has an alpha channel in whichever way.
        """
        if not hasattr(self.data.IHDR, "_has_alpha_channel"):
            self.scan_ihdr()  # parse the IHDR chunk if not already done
            _ = self.data.IHDR.channel_count  # Ensure colour type is processed
        # To avoid handling palettes as done in PyPNG, give alpha "directly"
        # https://github.com/drj11/pypng/blob/main/code/png.py#L1948-L1953
        has_alpha = self.data.IHDR._has_alpha_channel  # based on colour type
        if self.data.IHDR._has_colourmap:
            # Allow alpha to switch on if tRNS chunk present
            has_alpha |= self.has_chunk(chunk_type="tRNS")
        return has_alpha

    def any_semitransparent_idat(self, nonzero: bool = True):
        """
        Whether there are any non-255 values in the alpha channel of the PNG,
        determined from IDAT chunk alone. If not, the alpha channel serves no
        purpose in practice, and the image may be considered non-transparent.

        If ``nonzero`` is True (the default), check for semitransparent, rather
        than nontransparent values (i.e. ``0 < A < 255`` rather than ``0 <= A < 255``).

        Note: presumes :meth:`~range_streams.codecs.png.PngStream.alpha_as_direct` has
        already been called, so the image is known to have 4 channels.

        Args:
          nonzero : Whether to return ``True`` only if the image has 'intermediate'
                    (between 0 and 255) values, otherwise whether they're below 255.
        """
        A = self.get_idat_data()[3::4]  # alpha channel values
        return any(0 < v < 255 for v in A) if nonzero else any(v < 255 for v in A)

    @property
    def channel_count_as_direct(self):
        """
        If the image is indexed on a palette, then the channel count in the IHDR
        will be 1 even though the underlying sample contains 3 channels (R,G,B).
        To avoid distinguishing 'direct' image channels (in IDAT) from 'indirect'
        (or computed, from tRNS) palette channels, check for a colour map and then
        check for a tRNS chunk to determine overall whether this image has an extra
        channel for transparency.
        """
        if self.data.IHDR.channel_count is None:
            self.scan_ihdr()  # parse the IHDR chunk if not already done
        # To avoid handling palettes as done in PyPNG, give channel count "directly"
        # https://github.com/drj11/pypng/blob/main/code/png.py#L1948-L1953
        channel_count = self.data.IHDR.channel_count  # based on colour type
        if self.data.IHDR._has_colourmap:
            # Allow alpha to switch on if tRNS chunk present
            channel_count = 3 + int(self.alpha_as_direct)
        return channel_count

    @property
    def bit_depth_as_direct(self):
        """
        Indexed images may report an IHDR bit depth other than 8, however the PLTE
        uses 8 bits per sample regardless of image bit depth, so override it to avoid
        distinguishing 'direct' bit depth from 'indirect' palette bit depth.
        """
        if self.data.IHDR.bit_depth is None:
            self.scan_ihdr()  # parse the IHDR chunk if not already done
        # To avoid handling palettes as done in PyPNG, give bit depth "directly"
        # https://github.com/drj11/pypng/blob/main/code/png.py#L1948-L1953
        return 8 if self.data.IHDR._has_colourmap else self.data.IHDR.bit_depth
