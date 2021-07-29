r"""
:mod:`range_streams.codecs` provides file format-specific ('codec') extensions
to the :mod:`range_streams` package.

The currently supported list of codecs is:
- .zip
- .conda (zip containing zstd-compressed tarballs, used for the conda package archives)
- .tar (uncompressed only)
- .png

There are planned extensions to other archive and image formats.
"""

from .conda import CondaStream
from .png import PngStream
from .tar import TarStream
from .zip import ZipStream

__all__ = [
    "ZipStream",
    "TarStream",
    "CondaStream",
    "PngStream",
]
