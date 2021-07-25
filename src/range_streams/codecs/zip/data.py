from struct import calcsize

# from zipfile: structCentralDir, structEndArchive, structEndArchive64, structFileHeader

__all__ = ["ZipData", "CentralDirectory"]

# DATA_ATTRS = ["start_sig", "end_sig"]


class SimpleDataClass:
    def __repr__(self):
        # attrs = {k: getattr(cls, k) for k in DATA_ATTRS if k in dir(cls)}
        attrs = {
            k: getattr(self, k)
            for k in dir(self)
            if not k.startswith("_")
            if not callable(getattr(self, k))
        }
        # return f"{cls.__name__} :: {getattr(cls, 'start_sig')}"
        return f"{self.__class__.__name__} :: {attrs}"

    def get_size(self):
        return calcsize(self.struct)

    @property
    def struct(self):
        raise NotImplementedError("SimpleDataClass must be subclassed with a struct")

    def __init__(self):
        self.start_pos = None


class CentralDirectoryRec(SimpleDataClass):
    """
    A class carrying attributes to describe the central directory of a zip file.
    Inherited by :class:`ZipData`
    """

    start_sig = b"PK\x01\x02"
    struct = "<4s4B4HL2L5H2L"  # structCentralDir
    # end_sig = b"PK\x05\x05"

    def __init__(self):
        super().__init__()
        self.entry_count = None


class LocalFileHeader(SimpleDataClass):
    """
    A class carrying attributes to describe the local file header(s) of a zip file.
    Inherited by :class:`ZipData`.
    """

    start_sig = b"PK\x03\x04"
    struct = "<4s2B4HL2L2H"  # structFileHeader


class Zip64EndOfCentralDirectoryRec(SimpleDataClass):
    start_sig = b"PK\x06\x06"
    struct = "<4sQ2H2L4Q"  # structEndArchive64


class EndOfCentralDirectoryRec(SimpleDataClass):
    start_sig = b"PK\x05\x06"
    struct = b"<4s4H2LH"  # structEndArchive


class ZipData:
    """
    A mixin class collecting other classes as attributes to provide format-specific
    information on zip files to the ZipStream class (alongside the generic stream
    behaviour it inherits from the RangeStream class).
    """

    def __init__(self):
        self.CTRL_DIR_REC = CentralDirectoryRec()
        self.LOC_F_H = LocalFileHeader()
        self.Z64_E_O_CTRL_DIR_REC = Zip64EndOfCentralDirectoryRec()
        self.E_O_CTRL_DIR_REC = EndOfCentralDirectoryRec()
