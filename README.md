# range-streams

Streaming via range requests in Python

## Outline of `RangeStream` data structure

A `RangeStream` is initialised by providing:

- a URL (to the file to be streamed)
- a client (e.g. `httpx.Client` or `requests.Session`)
- (optionally) a range, as either:
  - `ranges.Range` from the `python-ranges` package [recommended]
  - or a tuple of integers, presumed to be a half-open interval
    inclusive of start/exclusive of end as is common practice
    in Python — `[start, end)` in
    [interval notation](https://en.wikipedia.org/wiki/Interval_(mathematics)#Notations_for_intervals)

If no range is provided then the empty range `[0,0)` is presumed, and no bytes are requested
from the server: however since every range request returns the total content length, the resulting
`RangeStream` will be fully capable of seeking and calculating end-relative ranges.

Once initialised, either with a request for the default empty range or a non-empty range,
this range becomes the first entry in the `RangeDict` stored on the `._ranges` attribute
of the `RangeStream`.

### Option A: strictly disjoint `RangeStream`

The `RangeStream` _will not_ invoke any further range requests which overlap
an existing `RangeResponse` without first exhausting all the bytes in its response iterator.

- If you request the complete range of a file, it will not be possible to take advantage of
  the 'streaming' behaviour, as any further ranges specified will already be spanned by the
  first "complete file range", and so the entire file will be loaded into memory
- There is a strict one-to-one map per byte position to a particular response (if the position
  is in the `RangeStream`)

### Option B: degenerate `RangeStream`

The `RangeStream` _will_ invoke further range requests which overlap an existing `RangeResponse`
without first exhausting all the bytes in its response iterator.

- The same bytes will be downloaded again but in a separate response iterator, allowing them
  to be consumed separately.
- If you request the complete range of a file, it will be possible to take advantage of
  the 'streaming' behaviour, but any further ranges specified will already be spanned by the
  first "complete file range", and so the further ranges are effectively always duplicates
  (bandwidth inefficient, memory efficient)
- There is no longer a one-to-one map of a particular byte position and a particular response
  (for a position which is present in the `RangeStream`)
  - Instead the mapping may be either one-to-one or one-to-many [varying 'coverage']

Review: option A is more principled, and would best suit a use with a known file format,
as I had in mind (for zip files where the precise boundaries of files can be determined).

## Requires

- Python 3.8+

## See also

- [Motivation.md](https://github.com/lmmx/range-streams/blob/master/docs/Motivation.md)
- [TODO.md](https://github.com/lmmx/range-streams/blob/master/docs/TODO.md)
- [CONDA\_SETUP.md](https://github.com/lmmx/range-streams/blob/master/docs/CONDA_SETUP.md)
