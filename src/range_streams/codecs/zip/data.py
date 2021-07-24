from struct import calcsize

# from zipfile: structCentralDir, structEndArchive, structEndArchive64, structFileHeader

__all__ = ["ZipDataMixIn", "CentralDirectory"]

# DATA_ATTRS = ["start_sig", "end_sig"]


class SimpleDataClass:
    @classmethod
    def __repr__(cls):
        # attrs = {k: getattr(cls, k) for k in DATA_ATTRS if k in dir(cls)}
        attrs = {k: getattr(cls, k) for k in dir(cls) if not k.startswith("_")}
        # return f"{cls.__name__} :: {getattr(cls, 'start_sig')}"
        return f"{cls.__name__} :: {attrs}"

    def get_size(self):
        return calcsize(self.struct)

    @property
    def struct(self):
        raise NotImplementedError("SimpleDataClass must be subclassed with a struct")


class CentralDirectoryRec(SimpleDataClass):
    """
    A class carrying attributes to describe the central directory of a zip file.
    Inherited by :class:`ZipDataMixIn`
    """

    start_sig = b"PK\x01\x02"
    struct = "<4s4B4HL2L5H2L"  # structCentralDir
    # end_sig = b"PK\x05\x05"
    start_pos = None


class LocalFileHeader(SimpleDataClass):
    """
    A class carrying attributes to describe the local file header(s) of a zip file.
    Inherited by :class:`ZipDataMixIn`.
    """

    start_sig = b"PK\x03\x04"
    struct = "<4s2B4HL2L2H"  # structFileHeader
    start_pos = None


class Zip64EndOfCentralDirectoryRec(SimpleDataClass):
    start_sig = b"PK\x06\x06"
    struct = "<4sQ2H2L4Q"  # structEndArchive64
    start_pos = None


class EndOfCentralDirectoryRec(SimpleDataClass):
    start_sig = b"PK\x05\x06"
    struct = b"<4s4H2LH"  # structEndArchive
    start_pos = None


class ZipDataMixIn:
    """
    A mixin class collecting other classes as attributes to provide format-specific
    information on zip files to the ZipStream class (alongside the generic stream
    behaviour it inherits from the RangeStream class).
    """

    CTRL_DIR_REC = CentralDirectoryRec()
    LOC_F_H = LocalFileHeader()
    Z64_E_O_CTRL_DIR_REC = Zip64EndOfCentralDirectoryRec()
    E_O_CTRL_DIR_REC = EndOfCentralDirectoryRec()
