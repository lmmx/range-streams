## TODO

- Firstly distinguish it by renaming to `RangeStream` (it's no longer going to
  comprise only a single response)

Regarding how to extend `ResponseStream` classes to work with range requests:

- Multiple requests would need to be supported on the object
  - If I start by requesting a range `0-1` and then later decide I want `2-3`
    then it is necessary to store these.
  - Ranges will always be consecutive, but separate ranges will not necessarily
    be contiguous.
  - Where they are, their bytes can be merged (conjoined) by merging their generators
    (i.e. from the `iter_bytes` methods of each)
- If a read operation would exceed the range already obtained, send another range request
- Support "reading backwards" from the end (e.g. to detect a 'magic number' byte signature)
