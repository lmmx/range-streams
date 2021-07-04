# range-streams

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
`RangeDict` stored on the `._ranges` attribute.

## Example

```py
from range_streams import RangeStream, example_url
import httpx
from ranges import Range
c = httpx.Client()
s = RangeStream(url=example_url, client=c)
rng = Range(0,3)
s.handle_byte_range(rng)

print(s._ranges)
```
⇣
```
RangeDict{
  RangeSet{Range[0, 3)}: <range_streams.range_response.RangeResponse object>
}
```

## Requires

- Python 3.8+

## See also

- [Motivation.md](https://github.com/lmmx/range-streams/blob/master/docs/Motivation.md):
  background on the idea and why you would want to use this technique
- [Design.md](https://github.com/lmmx/range-streams/blob/master/docs/Design.md):
  technical overview on how disjoint ranges are represented and how intersecting ranges are handled
- [TODO.md](https://github.com/lmmx/range-streams/blob/master/docs/TODO.md)
- [CONDA\_SETUP.md](https://github.com/lmmx/range-streams/blob/master/docs/CONDA_SETUP.md)
