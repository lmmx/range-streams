from __future__ import annotations

from struct import calcsize

from ranges import Range

__all__ = ["PngData"]


class SimpleDataClass:
    """
    Provide a neat repr and common methods for the classes which become instance
    attributes of :class:`PngData`.

    (Note: Duplicate of the zip codec class of the same name)
    """

    def __repr__(self):
        attrs = {
            k: getattr(self, k)
            for k in dir(self)
            if not k.startswith("_")
            if not callable(getattr(self, k))
        }
        return f"{self.__class__.__name__} :: {attrs}"

    def get_size(self):
        return calcsize(self.struct)

    @property
    def struct(self):
        raise NotImplementedError("SimpleDataClass must be subclassed with a struct")

    def __init__(self):
        # self.start_pos: int | None = None
        pass


class IHDRInfo:
    _IHDR_WIDTH = 0
    _IHDR_HEIGHT = 1
    _IHDR_BIT_DEPTH = 2
    _IHDR_COLOUR_TYPE = 3
    _IHDR_COMPRESSION = 4
    _IHDR_FILTER_METHOD = 5
    _IHDR_INTERLACING = 6


class IHDRChunk(SimpleDataClass):
    """
    A class carrying attributes to describe the IHDR header of a PNG file.
    Used in :class:`PngData`, and updated with the number of channels in
    the PNG once this is identified.

    The fields are: width (4 bytes), height (4 bytes), bit depth (1 byte),
    colour type (1 byte), compression method (1 byte), filter method (1 byte),
    interlacing method (1 byte); totalling 13 bytes.
    """

    start_pos = 16
    end_pos = 29
    struct = ">IIBBBBB"
    parts = IHDRInfo

    def __init__(self):
        super().__init__()
        self.width: int | None = None
        self.height: int | None = None
        self.bit_depth: int | None = None
        self.colour_type: int | None = None
        self.compression: int | None = None
        self.filter_method: int | None = None
        self.interlacing: int | None = None

    @property
    def channel_count(self) -> int | None:
        if self.colour_type is None:
            # Early return! This is an edge case (IHDR chunk not parsed)
            # Should only occur when printing the __repr__ before parsing
            return None
        elif not hasattr(self, "_channels"):
            self.count_channels()
        return self._channels

    def count_channels(self) -> None:
        """
        Calculate channel count (e.g. RGB=3, RGBA=4) from colour type,
        and populate the :attr:`_channels` attribute (accessible via the
        :attr:`channel_count` property).
        """
        if self.colour_type is None:
            raise ValueError("Process the IHDR chunk before counting channels")
        self._has_colourmap: bool = bool(self.colour_type & 1)
        self._is_grayscale: bool = not (self.colour_type & 2)
        self._has_alpha_channel: bool = bool(self.colour_type & 4)
        self._colour_channel_count: int = (
            1 if (self._is_grayscale or self._has_colourmap) else 3
        )
        self._channels: int = self._colour_channel_count + int(self._has_alpha_channel)
        return


class PngData:
    """
    A class collecting other classes as attributes to provide format-specific
    information on PNG files to :class:`PngStream` (alongside the generic
    stream behaviour it inherits from :class`RangeStream`).
    """

    def __init__(self):
        self.IHDR = IHDRChunk()
        # self.PLTE = PLTEChunk()
        # self.IDAT = IDATChunk()
        # self.IEND = IENDChunk()
        # self.ancillary_chunks = AncillaryChunks()


class PngChunkInfo:
    _meta_chunk_total_size = 4 * 3  # Three 4-byte chunks (length, type, CRC)

    def __init__(self, type: str, start: int, length: int):
        self.start: int = start
        self.type: str = type
        self.length: int = length

    @property
    def end(self):
        """
        Exclusive end, i.e. for a half-closed range ``[start, end)``.
        """
        return self.start + self.length + self._meta_chunk_total_size

    def __repr__(self):
        attrs = {
            k: getattr(self, k)
            for k in dir(self)
            if not k.startswith("_")
            # if not callable(getattr(self, k))
        }
        return f"{self.__class__.__name__} :: {attrs}"

    @property
    def data_range(self):
        """
        Range on the parent :class`PngStream` of the chunk data.
        """
        data_start = self.start + (4 * 2)
        data_end = self.end - 4
        return Range(data_start, data_end)
