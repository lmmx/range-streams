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
    in Python
    - `[start, end)` in
      [interval notation](https://en.wikipedia.org/wiki/Interval_(mathematics)#Notations_for_intervals)

If no range is provided then the empty range `[0,0)` is presumed, and no bytes are requested
from the server: however since every range request returns the total content length, the resulting
`RangeStream` will be fully capable of seeking and calculating end-relative ranges.

Once initialised, 

## See also

- [Motivation.md](https://github.com/lmmx/range-streams/blob/master/docs/Motivation.md)
- [TODO.md](https://github.com/lmmx/range-streams/blob/master/docs/TODO.md)
- [CONDA\_SETUP.md](https://github.com/lmmx/range-streams/blob/master/docs/CONDA_SETUP.md)
