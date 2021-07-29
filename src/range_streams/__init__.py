r"""
:mod:`range_streams` provides file-like object handling through
an API familiar to users of the standard library
:mod:`io` module.  It uses :class:`~ranges.Range`, :class:`~ranges.RangeSet`,
and :class:`~ranges.RangeDict` classes (from the externally maintained
`python-ranges <https://python-ranges.readthedocs.io/en/latest/>`_ library)
to represent and look up range operations in an efficient linked
list data structure.

Servers with support for `HTTP range requests
<https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests>`_
can provide partial content requests, avoiding the need to download
and consume linearly from the start of a file when streaming,
or without needing to download the entire file (non-streaming requests).

A :class:`~range_streams.stream.RangeStream` is initialised by providing:

- a URL (the file to be streamed)
- (optionally) a client (:class:`httpx.Client`), or else a fresh one
  is created
- (optionally) a range, as either:
  :class:`~ranges.Range` from the `python-ranges` package [recommended];
  or a tuple of integers, presumed to be a half-open interval
  inclusive of start/exclusive of stop as is common practice
  in Python — ``[start, stop)`` in `interval notation
  <https://en.wikipedia.org/wiki/Interval_(mathematics)#Notations_for_intervals>`_.

If no range (or the empty range) is given, a HTTP HEAD request will be
sent instead of a GET request, to check the total length of the file being streamed.
Either way therefore determines the total file length upon initialisation
(:attr:`~range_streams.stream.RangeStream.total_bytes`, also available as the range spanning
the entire file :attr:`~range_streams.stream.RangeStream.total_range`).

The following example shows the basic setup for a single range.

    >>> from ranges import Range
    >>> from range_streams import RangeStream, _EXAMPLE_URL
    >>> s = RangeStream(url=_EXAMPLE_URL) # doctest: +SKIP
    >>> rng = Range(0,3) # doctest: +SKIP
    >>> s.add(rng) # doctest: +SKIP
    >>> s.ranges # doctest: +SKIP
    RangeDict{RangeSet{Range[0, 3)}: RangeResponse ⠶ [0, 3) @ 'example_text_file.txt' from github.com}

Once a request is made for a non-empty range, the :class:`~range_streams.stream.RangeStream`
acquires the first entry in the :class:`~ranges.RangeDict` stored on the
:attr:`~range_streams.stream.RangeStream.ranges` attribute. This gates access
to the internal ``_ranges`` attribute :class:`~ranges.RangeDict`), which takes
into account whether the bytes in each range's
:class:`~range_streams.response.RangeResponse` are exhausted
or removed due to overlap with another range. See the docs for further details.

Further ranges are requested by simply calling the :meth:`~range_streams.stream.RangeStream.add`
method with another :class:`~ranges.Range` object. To create this implicitly, you can
simply provide a byte range to the `add` method as a tuple of two integers,
which will be interpreted per the usual convention for ranges in Python,
as an ``[a,b)`` half-open interval.

    >>> s.add(byte_range=(7,9)) # doctest: +SKIP
    >>> s.ranges # doctest: +SKIP
    RangeDict{
      RangeSet{Range[0, 3)}: RangeResponse ⠶ [0, 3) @ 'example_text_file.txt' from github.com,
      RangeSet{Range[7, 9)}: RangeResponse ⠶ [7, 9) @ 'example_text_file.txt' from github.com
    }

Codecs are available for ``.zip`` (:class:`~range_streams.codecs.zip.ZipStream`) and ``.conda``
(:class:`~range_streams.codecs.conda.CondaStream`) archives, which will read and
name the ranges corresponding to the archive's contents file list upon initialisation.

    >>> from range_streams import _EXAMPLE_ZIP_URL
    >>> from range_streams.codecs import ZipStream
    >>> s = ZipStream(url=_EXAMPLE_ZIP_URL) # doctest: +SKIP
    >>> s.ranges # doctest: +SKIP
    RangeDict{
      RangeSet{Range[51, 62)}: RangeResponse ⠶ "example_text_file.txt" [51, 62) @ 'example_text_file.txt.zip' from github.com
    }

The ``.conda`` format is just a particular type of zip for Python packages on the conda
package manager (containing JSON and Zstandard-compressed tarballs):

    >>> from range_streams.codecs import CondaStream
    >>> EXAMPLE_CONDA_URL = "https://repo.anaconda.com/pkgs/main/linux-64/progressbar2-3.34.3-py27h93d0879_0.conda" # doctest: +SKIP
    >>> s = CondaStream(url=EXAMPLE_CONDA_URL) # doctest: +SKIP
    >>> s.ranges # doctest: +SKIP
    RangeDict{
      RangeSet{Range[77, 6427)}: RangeResponse ⠶ "info-progressbar2-3.34.3-py27h93d0879_0.tar.zst" [77, 6427) @ 'progressbar2-3.34.3-py27h93d0879_0.conda' from repo.anaconda.com
      RangeSet{Range[6503, 39968)}: RangeResponse ⠶ "pkg-progressbar2-3.34.3-py27h93d0879_0.tar.zst" [6503, 39968) @ 'progressbar2-3.34.3-py27h93d0879_0.conda' from repo.anaconda.com
      RangeSet{Range[40011, 40042)}: RangeResponse ⠶ "metadata.json" [40011, 40042) @ 'progressbar2-3.34.3-py27h93d0879_0.conda' from repo.anaconda.com
    }

- Note that unlike zips, tarballs use `solid compression
  <https://en.wikipedia.org/wiki/Solid_compression>`_ meaning they are not
  amenable to range request (you could but there'd be no benefit, `to my understanding
  <https://github.com/lmmx/range-streams/issues/24#issuecomment-888309932>`_).

A further codec handles PNG images (a file format composed of 'chunks' of different
types). The metadata can be identified from looking in the IHDR chunk and checking
for the presence of other chunks. Some properties are made available 'as direct'
(i.e. reliably, regardless of the specific PNG compression) mimicking `the approach
<https://github.com/drj11/pypng/blob/9946bcffe19a8d34115971210fad0671e73b66e1/code/png.py#L1895-L1938>`_
of the PyPNG library.

    >>> from range_streams import _EXAMPLE_PNG_URL
    >>> from range_streams.codecs import PngStream
    >>> s = PngStream(url=_EXAMPLE_PNG_URL) # doctest: +SKIP
    >>> s.alpha_as_direct # doctest: +SKIP
    True
    >>> s.channel_count_as_direct # doctest: +SKIP
    4
    >>> s.chunks # doctest: +SKIP
    {'IHDR': [PngChunkInfo :: {'data_range': Range[16, 29), 'end': 33, 'length': 13, 'start': 8, 'type': 'IHDR'}],
     'zTXt': [PngChunkInfo :: {'data_range': Range[41, 1887), 'end': 1891, 'length': 1846, 'start': 33, 'type': 'zTXt'}],
     'iCCP': [PngChunkInfo :: {'data_range': Range[1899, 2287), 'end': 2291, 'length': 388, 'start': 1891, 'type': 'iCCP'}],
     'bKGD': [PngChunkInfo :: {'data_range': Range[2299, 2305), 'end': 2309, 'length': 6, 'start': 2291, 'type': 'bKGD'}],
     'pHYs': [PngChunkInfo :: {'data_range': Range[2317, 2326), 'end': 2330, 'length': 9, 'start': 2309, 'type': 'pHYs'}],
     'tIME': [PngChunkInfo :: {'data_range': Range[2338, 2345), 'end': 2349, 'length': 7, 'start': 2330, 'type': 'tIME'}],
     'tEXt': [PngChunkInfo :: {'data_range': Range[2357, 2382), 'end': 2386, 'length': 25, 'start': 2349, 'type': 'tEXt'}],
     'IDAT': [PngChunkInfo :: {'data_range': Range[2394, 5108), 'end': 5112, 'length': 2714, 'start': 2386, 'type': 'IDAT'}],
     'IEND': [PngChunkInfo :: {'data_range': Range[5120, 5120), 'end': 5124, 'length': 0, 'start': 5112, 'type': 'IEND'}]}
    >>> s.data.IHDR # doctest: +SKIP
    IHDRChunk :: {'bit_depth': 8, 'channel_count': 4, 'colour_type': 6, 'compression': 0, 'end_pos': 29, 'filter_method': 0, 'height': 100, 'interlacing': 0, 'start_pos': 16, 'struct': '>IIBBBBB', 'width': 100}
    >>> s.get_idat_data()[:4] # doctest: +SKIP
    [153, 0, 0, 255]
"""

# Get classes into package namespace but exclude from __all__ so Sphinx can access types

from . import codecs, http_utils, overlaps, range_utils
from .request import RangeRequest
from .response import RangeResponse
from .stream import RangeStream

__all__ = [
    "stream",
    "request",
    "response",
    "http_utils",
    "overlaps",
    "range_utils",
    "codecs",
]

__author__ = "Louis Maddox"
__license__ = "MIT"
__description__ = "Streaming via range requests."
__url__ = "https://github.com/lmmx/range-streams"
__uri__ = __url__
__email__ = "louismmx@gmail.com"

_EXAMPLE_DATA_URL = "https://github.com/lmmx/range-streams/raw/master/data/"
_EXAMPLE_URL = f"{_EXAMPLE_DATA_URL}example_text_file.txt"
_EXAMPLE_ZIP_URL = f"{_EXAMPLE_DATA_URL}example_text_file.txt.zip"
_EXAMPLE_TAR_URL = f"{_EXAMPLE_DATA_URL}data.tar"
# _EXAMPLE_TAR_GZ_URL = f"{_EXAMPLE_TAR_URL}.gz"
# _EXAMPLE_TAR_BZ2_URL = f"{_EXAMPLE_TAR_URL}.bz2"
_EXAMPLE_PNG_URL = f"{_EXAMPLE_DATA_URL}red_square_rgba_semitransparent.png"
