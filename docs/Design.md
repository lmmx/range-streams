# Design notes for `RangeStream`

## Key Considerations

When it comes to handling ranges, the key design choice is regarding the central issue of how
overlapping ranges are handled.

1. Whether to be strict about keeping ranges disjoint
2. Whether to permit reallocation of a given range

One possibility for `RangeStream` would be not to invoke any further range requests which overlap
an existing `RangeResponse` without first exhausting all the bytes in its response iterator.
However, since the requests involved are streaming GET requests, there is no data downloaded
for a given iterator, and it makes more sense to simply re-define (re-request and overwrite)
or truncate it (i.e. ensure the iterator stops early).

- If instead we chose to "trim" already-requested ranges by reading them in, you would end up
  in the absurd situation of reading through [potentially large] regions of data which had been
  downloaded expressly to discard. Indeed, if you requested the complete range of a file in such
  a data structure, it would not be possible to take advantage of the 'streaming' behaviour at all,
  as any further ranges specified will already be spanned by the first "complete file range", and
  so the entire file would be loaded into memory when reading ranges near the end of the file.

The one benefit of such a "anti-re-requesting" data structure would be that the `RangeDict` keys
could be expected to reliably maintain their initialised values (as a singleton `RangeSet`
containing only the provided `Range`).

However, with careful handling (and a good test suite) this reliability can be ensured with a
more efficient and "re-requesting friendly" approach.

### Potentially degenerate `RangeStream`

If overlaps are permitted to be handled, then we have 3 options (all of which are available
through the `pruning_level` parameter initialised on `RangeStream`).

- Pruning level 0: "replant"
  - If a new range overlaps an existing range:
    - **(H)** at the existing head, then it is re-requested with this head removed (or "replanted")
    - **(T)** at the existing tail, then it is marked so that its iterator will stop early (with a
      "tail mark"), and is reported as if it was truncated (even though its `RangeResponse` will
      still store the originally requested range 'un-truncated')
    - **(HTT)** completely, or 'head-to-tail', then the existing range is truncated to just the
      'upstream' part
  - If any of the above scenarios would result in an empty range, then it is "burned" instead
- Pruning level 1: "burn"
  - If a new range overlaps an existing range, then it is simply "burned" (i.e. deleted from the
    `RangeDict`)
- Pruning level 2: "strict"
  - If a new range overlaps an existing range, then a `ValueError` is raised

In these scenarios, the overlaps are calculated against the "external" ranges, which are
modified upon reading. If a given range has been requested, but then was read, then those
positions which were read past will no longer be subject to overlap checks (they are no
longer 'seen' by the overlap handler).

For a file format whose precise boundaries can be determined (such as zip files), with a
careful approach each position can be efficiently accessed once only using this library.

### Every position has at most one associated "primary range"

Each position in a range that was requested will either be "read past" (indicated by a positive
offset), "still to read" (i.e. not read past), or "not to be read" (indicated by the
"tail mark" which effectively truncates a range, and is set to avoid overlaps when
registering a new range).

- The offset that has been read into a given range is given by
  `RangeResponse.tell()` (a method the
  [`io.BytesIO`](https://docs.python.org/3.8/library/io.html#io.BytesIO) stream
  [inherits](https://docs.python.org/3.8/library/io.html#io.IOBase.tell) from `io.IOBase`)
- A second offset is stored for each range from its 'tail', indicating that the
  range can be considered "trimmed shorter" (i.e. any consumer should stop early).
  - When an overlap would occur, this tail offset allows the overlapped positions to
    be re-assigned to be associated with the newer range.
- Whether a range still has bytes left to be read is reported by the `is_consumed()` method
  on the `RangeResponse` (which is stored in the values of the `RangeDict` in a `RangeStream`
  at the `Range` key for the positions in question).

## File-like streams

The `RangeStream` gives a file-like object (commonly referred to in the Python standard library
as `fp`), which is complicated by the fact that this means it must have a singular position to
return from `tell()`, despite being composed of multiple ranges able to be iterated independently.

By design this is disallowed, only a single range should be used at a time, so `tell()`, `read()`,
and `seek()` will behave as expected for a file on disk.

The `_active_range` attribute stores the most recently registered range, and the
`active_range_response` stores the property at that range. Note that the `_active_range` is
an _internal_ range (meaning it comes from the `_ranges: RangeDict` and will not change when
read, though it will reflect changes due to the tail mark which are fundamental to the
range itself). The _external_ range changes when bytes are read from the response it
points to in the external `ranges: RangeDict`.

---

## Range comparison

There are 4 distinct ways of comparing ranges in a `RangeStream` (checking for membership):

### `RangeStream._ranges`

`RangeStream._ranges` is a `RangeDict` of all the `Range`s.

- The keys of this `RangeDict` should be singleton `RangeSet`s containing only the initialised
  `Range`, though the start and end positions may change after overlap handling.
- The values are `RangeRequest` objects storing the request sent and response received along
  with the initialised range (which never changes).
- The ranges in the keys do not change when the `RangeResponse` is read

Comparing to the `_ranges` attribute therefore compares against the set of ranges requested
so far from the file (note: not to be confused with the union of these ranges, which is empty
for any ranges which are not directly consecutive).

This is known as the "internal" `RangeDict`, and its keys do not reflect modifications made when the
range is 'read'. They only reflect modifications made to avoid overlaps.

### `RangeStream.ranges`

This is the "external" property (with read-only keys) which gates access to `_ranges`, and
reflects the extent to which ranges have been consumed (i.e. when the `RangeResponse` of
an entry is read through, the key is updated so the start position matches the `tell` position
from the response iterator).

### `RangeStream.spanning_range`

`RangeStream.spanning_range` is a property defined once the first range request has been
completed, and is either the initialised range (which may be the empty range) or if
further ranges have been requested, the range which spans the minimum/maximum terminus of
the "first and last" ranges in the `RangeStream.ranges` keys (i.e. ranges with lowest
start/highest end positions).

Note that this property is calculated from the external ranges, and therefore is liable to
change when the response iterators are read (and indeed is certain to change if the response
is the "first" range in the `RangeStream`).

Comparing to the `spanning_range` property therefore compares against a set which is not
necessarily fully covered by the ranges requested in the `RangeStream.ranges: RangeDict`,
but merely is within the extremes of those ranges. (There may be gaps).

### `RangeStream.total_range`

`RangeStream.total_range` is a property defined once the first range request has been
completed, and is simply the range from the start of the file (position 0) to the
end of the file, i.e. `[0, RangeStream.total_bytes)`.

Comparing to the `total_range` property therefore compares against a set which is not
necessarily fully covered (or even at all: the `RangeStream` may be completely empty!)
by the ranges requested in the `RangeStream`'s `ranges` (or `_ranges`) RangeDict.
