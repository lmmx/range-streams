r"""
files available on a server with support for HTTP range requests
<https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests>
enabling partial content requests on a 'need to know basis',
without having to download and consume linearly from the start of
a file when streaming, or without needing to download the entire
file (non-streaming requests).

:mod:`range_streams` provides file-like object handling through
an API familiar to users of the standard library
:mod:`io` module.  It uses Range, RangeSet, and RangeDict classes
to represent and look up range operations in an efficient linked
list data structure from the externally maintained python-ranges
library.

A `RangeStream` is initialised by providing:

- a URL (the file to be streamed)
- a client (e.g. `httpx.Client` or `requests.Session`)
- (optionally) a range, as either:
  - `ranges.Range` from the `python-ranges` package [recommended]
  - or a tuple of integers, presumed to be a half-open interval
    inclusive of start/exclusive of stop as is common practice
    in Python — `[start, stop)` in interval notation
    <https://en.wikipedia.org/wiki/Interval_(mathematics)#Notations_for_intervals>

Since every range request returns the total content length, the
`RangeStream` will become capable of seeking to negative-valued
ranges (whose positions are in respect to the end) after
fulfilling its first range request.

If no range is provided upon initialisation then the range
defaults to `[0,0)`, the empty range, and a request will be sent
to the server for this (valid) range, whose only result will be
to set the total file length on the `_length` attribute of
`RangeStream` (accessed through the `total_bytes` property).

Once a request is made for a non-empty range, the `RangeStream`
acquires the first entry in the `RangeDict` stored on the
`._ranges` attribute. When using the ranges, you should access
the `ranges` property (instead of the internal `_ranges`
attribute), which takes into account whether the bytes in each
range's `RangeResponse` are exhausted or removed due to overlap
with another range. See the design docs for further details.

The following example shows the basic setup for a single range.

    >>> import httpx
    >>> from ranges import Range
    >>> from range_streams import RangeStream, _EXAMPLE_URL
    >>> c = httpx.Client()
    >>> s = RangeStream(url=_EXAMPLE_URL, client=c)
    >>> rng = Range(0,3)
    >>> s.add(rng)
    >>> s.ranges
    RangeDict{
      RangeSet{Range[0, 3)}: RangeResponse ⠶ [0, 3) @ 'example_text_file.txt' from github.com
    }

Further ranges are requested by simply calling `RangeStream.add` with another Range
object. You can also provide a byte range to the `add` method as a tuple of
two integers, which will be interpreted per the usual convention for ranges in Python,
as a `[a,b)` half-open interval.

    >>> s.add(byte_range=(7,9))
    >>> s.ranges
    RangeDict{
      RangeSet{Range[0, 3)}: RangeResponse ⠶ [0, 3) @ 'example_text_file.txt' from github.com,
      RangeSet{Range[7, 9)}: RangeResponse ⠶ [0, 3) @ 'example_text_file.txt' from github.com
    }
"""

from .range_stream import *

__author__ = "Louis Maddox"
__license__ = "MIT"
__description__ = "Streaming via range requests."
__url__ = "https://github.com/lmmx/range-streams"
__uri__ = __url__
__email__ = "louismmx@gmail.com"

_EXAMPLE_URL = (
    "https://github.com/lmmx/range-streams/raw/"
    "bb5e0cc2e6980ea9e716a569ab0322587d3aa785/example_text_file.txt"
)
