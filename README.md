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

## Requires

- Python 3.8+

## See also

- [Motivation.md](https://github.com/lmmx/range-streams/blob/master/docs/Motivation.md):
  background on the idea and why you would want to use this technique
- [Design.md](https://github.com/lmmx/range-streams/blob/master/docs/Design.md):
  technical overview on how disjoint ranges are represented and how intersecting ranges are handled
- [TODO.md](https://github.com/lmmx/range-streams/blob/master/docs/TODO.md)
- [CONDA\_SETUP.md](https://github.com/lmmx/range-streams/blob/master/docs/CONDA_SETUP.md)
