When it comes to handling ranges, there are two main design choices for the core issue of
overlapping ranges, which dictates what the structure looks like as well as the behaviour
(or "form follows function").

### Option A: strictly disjoint `RangeStream`

The `RangeStream` _will not_ invoke any further range requests which overlap
an existing `RangeResponse` without first exhausting all the bytes in its response iterator.

- If you request the complete range of a file, it will not be possible to take advantage of
  the 'streaming' behaviour, as any further ranges specified will already be spanned by the
  first "complete file range", and so the entire file will be loaded into memory
- There is a strict one-to-one map per byte position to a particular response (if the position
  is in the `RangeStream`)
  - As a result, `RangeDict` keys can be reliably expected to maintain their initialised values
    (a singleton `RangeSet` containing only the provided `Range`)

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
  - As a result, `RangeDict` keys are subject to mutate
    - e.g. a `RangeDict` initialised with the range `[0,3)` to which another range
      `[1,2)` is added will split into a `RangeSet` of two `Range`s: `[0, 1)` and `[2, 3)`
    - Note that the original `Range` will always be retained in the `RangeRequest` which is
      stored as the value of each `RangeDict` item (so if a `RangeSet` key does degenerate
      into multiple ranges, its initialised value can always be retrieved in `.request.range`).

### `RangeStream` opts for strictly disjoint ranges

Review: option A is more principled, and would best suit a use with a known file format,
as I had in mind (for zip files where the precise boundaries of files can be determined).

Rather than raising an error and borking on overlapping ranges, `RangeStream` takes the following
approach:

### Every byte in a range is either available or consumed

Since it can only be consumed from the head, this is achieved by storing a positive offset
for each range which is incremented on reading.

### Every range has at most one associated "primary range"

A second offset is stored for each range from its 'tail', indicating that the
range can be considered "trimmed shorter" (i.e. any consumer should stop early).

When an overlap would occur, this tail offset allows the overlapped positions to
be re-assigned to be associated with the newer range.

### Overlaps at the tail of a pre-existing `RangeResponse` erase the pre-existing tail

Every range's tail offset starts at 0 (i.e. no early stopping when consuming).

If a new range is registered on the same stream with overlapping bytes to a pre-existing
range's tail, then the overlap is removed from the pre-existing tail by incrementing
the tail offset. As already mentioned, any bytes in the intersection become associated
with the newer range instead of the 'tail-trimmed' range.

### Overlaps at the head of a pre-existing `RangeResponse` are reduced and chained

If a new range overlaps at the 'head' of a pre-existing `RangeResponse`, the new
range is shortened by the length of the overlap and the bytes that would have been
requested are instead taken from the pre-existing head (note: only if the head is 
unconsumed) by
[splitting the iterable](https://docs.python.org/3/library/itertools.html#itertools.islice).

- To do so, the standard access to the iterable is 'gated' by an attribute accessor
  which redirects to the split iterable if one exists.

Overlaps in the body of a pre-existing `RangeResponse` are treated equivalently to overlaps
at a pre-existing head ('head' is simply understood to be the earliest unconsumed byte in the
range).

---

The rest is pretty straightforward: the `RangeStream` gives a file-like object (commonly
referred to in the Python standard library as `fp`), which is complicated by the fact that
this means it must have a singular position to return from `tell()`, despite being composed
of multiple ranges able to be iterated independently.

By design this is disallowed, only a single range should be used at a time, so
`tell()`, `read()`, and `seek()` will behave as expected for a file on disk.

---

## Range comparison

There are 3 distinct ways of comparing ranges in a `RangeStream` (checking for membership):

### `RangeStream._ranges`

`RangeStream._ranges` is a `RangeDict` of all the `Range`s (the keys of which should be
singleton `RangeSet`s containing only the initialised `Range` and values are `RangeRequest`
objects storing the request sent and response received along with the initialised range.

Comparing to the `_ranges` attribute therefore compares against the set of ranges requested
so far from the file (note: not the union of these ranges, which is empty for any ranges
which are not directly consecutive)

### `RangeStream.spanning_range`

`RangeStream.spanning_range` is a property defined once the first range request has been
completed, and is either the initialised range (which may be the empty range) or if
further ranges have been requested, the range which spans the minimum/maximum terminus of
the "first and last" ranges in the `RangeStream._ranges` keys (i.e. ranges with lowest
start/highest end positions).

Comparing to the `spanning_range` property therefore compares against a set which is not
necessarily fully covered by the ranges requested in the `RangeStream._ranges: RangeDict`,
but merely is within the extremes of those ranges.

### `RangeStream.total_range`

`RangeStream.total_range` is a property defined once the first range request has been
completed, and is simply the range from the start of the file (position 0) to the
end of the file, i.e. `[0, RangeStream.total_bytes)`.

Comparing to the `total_range` property therefore compares against a set which is not
necessarily fully covered (or even at all: the `RangeStream` may be completely empty!)
by the ranges requested in the `RangeStream._ranges: RangeDict`
