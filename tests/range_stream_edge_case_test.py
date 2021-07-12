from pytest import mark, raises
from ranges import Range

from range_streams import RangeStream

from .data import EXAMPLE_FILE_LENGTH
from .range_stream_core_test import (
    empty_range_stream,
    full_range_stream,
    make_range_stream,
)


def test_overlapping_ranges(empty_range_stream):
    s = empty_range_stream
    s.add(Range(0, 3))
    s.add(Range(1, 3))
    # TODO: determine correct behaviour to assert
    assert isinstance(s, RangeStream)


@mark.parametrize("start", [0])
@mark.parametrize("stop", [0, 5, EXAMPLE_FILE_LENGTH])
def test_range_from_empty_same_as_from_nonempty(start, stop, empty_range_stream):
    empty_range_stream.add(Range(start, stop))
    from_nonempty = make_range_stream(start, stop)
    assert empty_range_stream.list_ranges() == from_nonempty.list_ranges()


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
    full_range_stream.add(byte_range=Range(4, 6))
    assert full_range_stream.check_range_integrity() is None


def test_subrange_register_pass_full_stream(full_range_stream):
    """
    Full RangeStream's length should be checked so calling `register_range`
    on it should be fine
    """
    full_range_stream.register_range(rng=Range(4, 6), value=123)
    assert full_range_stream.check_range_integrity() is None


@mark.parametrize("start,stop", [(0, 1)])
@mark.parametrize("error_msg", ["Stream length must be set before registering a range"])
def test_class_register_range(start, stop, error_msg):
    """
    RangeStream class's length should not be checked until initialised as an instance,
    so calling `register_range` on the class itself should error out.
    """
    with raises(ValueError, match=error_msg):
        RangeStream.register_range(self=RangeStream, rng=Range(start, stop), value=123)


@mark.parametrize("start,stop", [(20, 30), (0, 100), (5, 15)])
@mark.parametrize("error_msg", [".*is not a sub-range of.*"])
def test_subrange(full_range_stream, start, stop, error_msg):
    with raises(ValueError, match=error_msg):
        full_range_stream.register_range(rng=Range(start, stop), value=123)


def test_nonduplicate_range_add(full_range_stream):
    """
    Design choice currently permits reassigning the full range if it was
    read, may change but for now just test to clarify behaviour. See issue #4.
    """
    _ = full_range_stream.read()
    full_range_stream.add(full_range_stream.total_range)


@mark.parametrize(
    "error_msg", ["Cannot get active range response.*self._active_range=.*"]
)
def test_bad_active_range_response(full_range_stream, error_msg):
    """
    Design choice currently permits reassigning the full range if it was
    read, may change but for now just test to clarify behaviour. See issue #4.
    """
    full_range_stream._active_range = 123
    with raises(ValueError, match=error_msg):
        full_range_stream.active_range_response


@mark.parametrize("error_msg", ["Cannot use total_range before setting _length"])
def test_total_range_sabotage_length(empty_range_stream, error_msg):
    """
    RangeStream class's `total_range` property should not work if the _length
    was somehow altered (not possible to access before initialisation).
    Not realistic so not a specific error.
    """
    empty_range_stream._length = None
    with raises(AttributeError, match=error_msg):
        empty_range_stream.total_range


@mark.parametrize("error_msg", ["Cannot use total_range before setting _length"])
def test_total_range_sabotage_length(empty_range_stream, error_msg):
    """
    RangeStream class's `total_range` property should not work if the _length
    was somehow altered (not possible to access before initialisation).
    Not realistic so not a specific error.
    """
    empty_range_stream._length = None
    with raises(AttributeError, match=error_msg):
        empty_range_stream.total_range


@mark.parametrize("error_msg", ["Cannot get active range response.*no active range.*"])
def test_empty_stream_tell_init(empty_range_stream, error_msg):
    with raises(ValueError, match=error_msg):
        empty_range_stream.tell()
