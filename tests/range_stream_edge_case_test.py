import httpx
from pytest import fixture, mark, raises
from ranges import Range

from range_streams import RangeStream

from .data import example_file_length, example_url
from .range_stream_core_test import (
    empty_range_stream,
    full_range_stream,
    make_range_stream,
)


def test_overlapping_ranges(empty_range_stream):
    s = empty_range_stream
    s.handle_byte_range(Range(0, 3))
    s.handle_byte_range(Range(1, 3))
    # TODO: determine correct behaviour to assert
    assert isinstance(s, RangeStream)


@mark.parametrize("start,stop", [(0, i) for i in (0, 5, example_file_length)])
def test_range_from_empty_same_as_from_nonempty(start, stop, empty_range_stream):
    from_empty = empty_range_stream
    from_empty.handle_byte_range(Range(start, stop))
    from_nonempty = make_range_stream(start, stop)
    # if stop > 9:
    #    print(f"{from_empty._ranges=}")
    #    print(f"{from_nonempty._ranges=}")
    #    raise ValueError # raise to emit the print statement
    assert from_empty.list_ranges() == from_nonempty.list_ranges()


@mark.parametrize("error_msg", ["Each RangeSet must contain 1 Range.*"])
def test_range_integrity_check_fails(full_range_stream, error_msg):
    """
    Putting a range “into” (i.e. with shared positions on) the central
    ‘mid-body’ of an existing range (without first trimming the existing
    range), will cause the existing range to automatically ‘split’ its
    RangeSet to ‘give way’ to the new range (this is the behaviour of
    RangeDict upon adding new keys whose range intersects the existing
    range key of a RangeSet, and means keys remain unique, but gives
    ‘loose ends’ as the singleton rangeset for the existing range
    splits into a doublet RangeSet of pre- and post- subranges)
    """
    with raises(ValueError, match=error_msg):
        full_range_stream._ranges.add(rng=Range(4, 6), value=123)
        full_range_stream.check_range_integrity()


def test_range_integrity_check_pass_empty_stream(empty_range_stream):
    empty_range_stream._ranges.add(rng=Range(4, 6), value=123)
    assert empty_range_stream.check_range_integrity() is None


def test_range_integrity_check_pass_full_stream(full_range_stream):
    full_range_stream.handle_byte_range(byte_range=Range(4, 6))
    assert full_range_stream.check_range_integrity() is None
