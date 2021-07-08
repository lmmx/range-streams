import httpx
from pytest import fixture, mark
from ranges import Range

from range_streams import RangeStream, example_url

from .range_stream_core_test import empty_range_stream, make_range_stream


def test_overlapping_ranges(empty_range_stream):
    s = empty_range_stream
    s.handle_byte_range(Range(0, 3))
    s.handle_byte_range(Range(1, 3))
    # TODO: determine correct behaviour to assert
    assert isinstance(s, RangeStream)


@mark.parametrize("start,stop", [(0, i) for i in (0, 5, 11)])
def test_range_from_empty_same_as_from_nonempty(start, stop, empty_range_stream):
    from_empty = empty_range_stream
    from_empty.handle_byte_range(Range(start, stop))
    from_nonempty = make_range_stream(start, stop)
    # if stop > 9:
    #    print(f"{from_empty._ranges=}")
    #    print(f"{from_nonempty._ranges=}")
    #    raise ValueError # raise to emit the print statement
    assert from_empty.list_ranges() == from_nonempty.list_ranges()
