from __future__ import annotations

from struct import calcsize

from ..share import COMPRESSIONS

# from zipfile: structCentralDir, structEndArchive, structEndArchive64, structFileHeader


__all__ = ["ZipData", "CentralDirectory"]


class SimpleDataClass:
    """
    Provide a neat repr and common methods for the classes which become instance
    attributes of :class:`ZipData`.
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


class CentralDirectoryRec(SimpleDataClass):
    """
    A class carrying attributes to describe the central directory of a zip file.
    Used in :class:`ZipData`, and updated with the number of entries (i.e.
    compressed files) in the zip once this is identified.
    """

    start_sig = b"PK\x01\x02"
    struct = "<4s4B4HL2L5H2L"  # structCentralDir
    # end_sig = b"PK\x05\x05"

    def __init__(self):
        super().__init__()
        self.entry_count: int | None = None
        self.size: int | None = None


class LocalFileHeader(SimpleDataClass):
    """
    A class carrying attributes to describe the local file header(s) of a zip file.
    Used in :class:`ZipData`.
    """

    start_sig = b"PK\x03\x04"
    struct = "<4s2B4HL2L2H"  # structFileHeader


class Zip64EndOfCentralDirectoryRec(SimpleDataClass):
    """
    (Unused) A class carrying attributes to describe the 'end of central directory
    record' of a zip file (the zip64 variant).
    """

    start_sig = b"PK\x06\x06"
    struct = "<4sQ2H2L4Q"  # structEndArchive64


class EndOfCentralDirectoryRec(SimpleDataClass):
    """
    A class carrying attributes to describe the 'end of central directory record' of a
    zip file. Used in :class:`ZipData`.
    """

    start_sig = b"PK\x05\x06"
    struct = b"<4s4H2LH"  # structEndArchive


class ZipData:
    """
    A class collecting other classes as attributes to provide format-specific
    information on zip files to the ZipStream class (alongside the generic stream
    behaviour it inherits from the RangeStream class).
    """

    def __init__(self):
        self.CTRL_DIR_REC = CentralDirectoryRec()
        self.LOC_F_H = LocalFileHeader()
        self.Z64_E_O_CTRL_DIR_REC = Zip64EndOfCentralDirectoryRec()
        self.E_O_CTRL_DIR_REC = EndOfCentralDirectoryRec()
