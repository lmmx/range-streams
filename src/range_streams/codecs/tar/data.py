from __future__ import annotations

from struct import calcsize

from ..share import COMPRESSIONS

__all__ = ["TarData"]


class SimpleDataClass:
    """
    Provide a neat repr and common methods for the classes which become instance
    attributes of :class:`TarData`.
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
        self.start_pos: int | None = None


# Subclasses of SimpleDataClass go here


class HeaderData(SimpleDataClass):
    _H_FILENAME_START = 0
    _H_FILE_MODE_START = 100
    _H_OWNER_UID_START = 108
    _H_GROUP_UID_START = 116
    _H_FILE_SIZE_START = 124
    _H_MTIME_START = 136
    _H_CHECKSUM_START = 148
    _H_LINK_INDICATOR_START = 156
    _H_LINKED_NAME_START = 157
    _H_FILENAME_SIZE = 100
    _H_FILE_MODE_SIZE = 8
    _H_OWNER_UID_SIZE = 8
    _H_GROUP_UID_SIZE = 8
    _H_FILE_SIZE_SIZE = 12
    _H_MTIME_SIZE = 12
    _H_CHECKSUM_SIZE = 8
    _H_LINK_INDICATOR_SIZE = 1
    _H_LINKED_NAME_SIZE = 100
    _H_PAD_SIZE = 512
    # Standard end-of-file padding is 2 padding records
    _H_END_PAD_SIZE = 2 * _H_PAD_SIZE


class TarData:
    """
    A class collecting other classes as attributes to provide format-specific
    information on zip files to the ZipStream class (alongside the generic stream
    behaviour it inherits from the RangeStream class).
    """

    def __init__(self):
        self.HEADER = HeaderData()  # overwrite with USTAR if USTAR detected
