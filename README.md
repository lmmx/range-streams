# range-streams

[![CI Status](https://github.com/lmmx/range-streams/actions/workflows/master.yml/badge.svg)](https://github.com/lmmx/range-streams/actions/workflows/master.yml)
[![Coverage](https://codecov.io/gh/lmmx/range-streams/branch/master/graph/badge.svg)](https://codecov.io/github/lmmx/range-streams)
[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Streaming via range requests in Python

## Outline of `RangeStream` data structure

A `RangeStream` is initialised by providing:

- a URL (the file to be streamed)
- a client (e.g. `httpx.Client` or `requests.Session`)
- (optionally) a range, as either:
  - `ranges.Range` from the `python-ranges` package [recommended]
  - or a tuple of integers, presumed to be a half-open interval
    inclusive of start/exclusive of stop as is common practice
    in Python — `[start, stop)` in
    [interval notation](https://en.wikipedia.org/wiki/Interval_(mathematics)#Notations_for_intervals)

Since every range request returns the total content length, the `RangeStream` will
become capable of seeking to negative-valued ranges (whose positions are in respect to the end)
after fulfilling its first range request.

If no range is provided upon initialisation then the range defaults to `[0,0)`, the empty range,
and a request will be sent to the server for this (valid) range, whose only result will be
to set the total file length on the `_length` attribute of `RangeStream` (accessed through the
`total_bytes` property).

Once a request is made for a non-empty range, the `RangeStream` acquires the first entry in the
`RangeDict` stored on the `._ranges` attribute. When using the ranges, you should access
the `ranges` property (instead of the internal `_ranges` attribute), which takes into account
whether the bytes in each range's `RangeResponse` are exhausted or removed due to overlap with
another range. See the design docs for further details.

## Example

- Adapted from
  [`tests/range_stream_core_test.py`](https://github.com/lmmx/range-streams/blob/master/tests/range_stream_core_test.py)

```py
import httpx

from range_streams import RangeStream, _EXAMPLE_URL

stream = RangeStream(url=_EXAMPLE_URL, client=httpx.Client())
stream.add(byte_range=(0,3)) # or pass ranges.Range(0,3)

stream.ranges
```
⇣
```py
RangeDict{
  RangeSet{Range[0, 3)}: RangeResponse ⠶ [0, 3) @ 'example_text_file.txt' from github.com
}
```

Further ranges are requested by simply calling `RangeStream.add` with another Range
object. You can also provide a byte range to the `add` method as a tuple
of two integers, which will be interpreted per the usual convention for ranges in Python,
as a `[a,b)` half-open interval.

```py
stream.add(byte_range=(7,9))
stream.ranges
```
⇣
```py
RangeDict{
  RangeSet{Range[0, 3)}: RangeResponse ⠶ [0, 3) @ 'example_text_file.txt' from github.com,
  RangeSet{Range[7, 9)}: RangeResponse ⠶ [7, 9) @ 'example_text_file.txt' from github.com
}
```

## Requires

- Python 3.8+

## See also

- [Motivation.md](https://github.com/lmmx/range-streams/blob/master/docs/Motivation.md):
  background on the idea and why you would want to use this technique
- [Design.md](https://github.com/lmmx/range-streams/blob/master/docs/Design.md):
  technical overview on how disjoint ranges are represented, how intersecting
  ranges are handled, and the different ways of comparing ranges on a `RangeStream`
- [TODO.md](https://github.com/lmmx/range-streams/blob/master/docs/TODO.md)
- [CONDA\_SETUP.md](https://github.com/lmmx/range-streams/blob/master/docs/CONDA_SETUP.md)
- [CONTRIBUTING.md](https://github.com/lmmx/range-streams/blob/master/.github/CONTRIBUTING.md)

> _range-streams_ is available from [PyPI](https://pypi.org/project/range-streams), and
> the code is on [GitHub](https://github.com/lmmx/range-streams)

- TODO: put up on PyPI!
