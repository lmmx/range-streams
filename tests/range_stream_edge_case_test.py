from pytest import mark, raises
from ranges import Range

from range_streams import RangeStream
from range_streams.range_utils import ranges_in_reg_order

from .data import EXAMPLE_FILE_LENGTH
from .range_stream_core_test import (
    centred_range_stream,
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


@mark.parametrize("test_pos", [0])
@mark.parametrize("overlapping_range", [Range(3, 7)])
@mark.parametrize(
    "pruning_level,expected_count", [(-1, None), (0, 1), (1, 1), (2, None)]
)
@mark.parametrize("error_msg_invalid", ["Pruning level must be 0, 1, or 2"])
@mark.parametrize(
    "error_msg_strict", ["Range overlap not registered due to strict pruning policy"]
)
def test_nonduplicate_range_add_with_pruning_Head_To_Tail(
    full_range_stream,
    test_pos,
    overlapping_range,
    pruning_level,
    expected_count,
    error_msg_invalid,
    error_msg_strict,
):
    """
    Although it is permitted to reassign a range if it was read (i.e. consumed), it may
    not be permitted to reassign a range if it has not been read.

    If the pruning policy is "strict" (`pruning_level` = 2) then attempting to do so
    will raise a ValueError.

    If the pruning policy is to "burn" (`pruning_level` = 1) then a range that is
    overlapped by another range being added will be deleted before the new range is
    added.

    If the pruning policy is to "replant" (`pruning_level` = 0) then a range that is
    overlapped by another range being added will be truncated (if the tail is
    overlapped, by incrementing a `tail_mark` on the internal Range stored) or
    re-requested (if the head is overlapped, by adding a replacement for a resized,
    disjoint version of the old range, before the new range is added).

    Vary the levels of pruning, check the results are as expected when adding an
    overlapping range, and catch the ValueError if the pruning mode is strict.

    The range `[3,7)` overlaps "Head To Tail" (HTT) with the range `[0,11)`, so
    it is expected that the counts of ranges in the RangeDict entry in the internal
    `_ranges` RangeDict should be 1 for both the pruning policies of "replant"/"burn"
    (`pruning_level` 0 and 1 respectively), since there is no remaining range
    left after trimming it, under the "replant" policy, the entry will be deleted,
    and for the "burn" policy all overlapped ranges are deleted. In both cases,
    a single entry will be left in the RangeDict.
    """
    full_range_stream.pruning_level = pruning_level
    if pruning_level in range(2):
        # 0 = replant, 1 = burn
        full_range_stream.add(overlapping_range)
        assert len(full_range_stream._ranges) == expected_count
        assert len(full_range_stream.ranges) == expected_count
    else:
        # 2 = strict, anything else is invalid
        error_msg = error_msg_strict if pruning_level == 2 else error_msg_invalid
        with raises(ValueError, match=error_msg):
            full_range_stream.add(overlapping_range)


@mark.parametrize("overlapping_range,test_pos", [(Range(2, 5), 3)])
@mark.parametrize(
    "pruning_level,expected_int_count,expected_ext_count",
    [(-1, None, None), (0, 2, 2), (1, 1, 1), (2, None, None)],
)
@mark.parametrize("error_msg_invalid", ["Pruning level must be 0, 1, or 2"])
@mark.parametrize(
    "error_msg_strict", ["Range overlap not registered due to strict pruning policy"]
)
def test_nonduplicate_range_add_with_pruning_Head(
    centred_range_stream,
    test_pos,
    overlapping_range,
    pruning_level,
    expected_ext_count,
    expected_int_count,
    error_msg_invalid,
    error_msg_strict,
):
    """
    If the pruning policy is to "replant" (`pruning_level` = 0) then a range that is
    overlapped at the "Head" (H) by another range being added will be re-requested
    (by adding a replacement for a resized, disjoint version of the old range, before
    the new range is added).

    Vary the levels of pruning, check the results are as expected when adding an
    overlapping range, and catch the ValueError if the pruning mode is strict.

    The range `[2,5)` overlaps the "Head" (H) of the range `[3,7)`, so it is expected
    that the counts of ranges in the RangeSet key in the internal `_ranges` RangeDict
    should differ for the pruning policies of "replant" and "burn" (pruning_level 0
    and 1 respectively). There will be remaining range left after trimming it, so
    the entry should remain when `pruning_level` is 0 ("replant") but be deleted when
    `pruning_level` is 1 ("burn").
    """
    centred_range_stream.pruning_level = pruning_level
    init_active_rng = centred_range_stream._active_range
    if pruning_level in range(2):
        # 0 = replant, 1 = burn
        centred_range_stream.add(overlapping_range)
        assert len(centred_range_stream._ranges) == expected_int_count
        assert len(centred_range_stream.ranges) == expected_ext_count
        if pruning_level == 0:
            # assert one of the RangeResponse ranges values in
            # centred_range_stream.ranges == overlapping_range
            # (because it was just requested) and the initial active range is
            # no longer in the list of internal ranges (because it was just burnt
            # and re-requested)
            assert centred_range_stream._active_range == overlapping_range
            rng_lst = ranges_in_reg_order(centred_range_stream._ranges)
            assert init_active_rng not in rng_lst
    else:
        # 2 = strict, anything else is invalid
        error_msg = error_msg_strict if pruning_level == 2 else error_msg_invalid
        with raises(ValueError, match=error_msg):
            centred_range_stream.add(overlapping_range)


@mark.parametrize("overlapping_range,test_pos", [(Range(5, 9), 5)])
@mark.parametrize(
    "pruning_level,expected_int_count,expected_ext_count",
    [(-1, None, None), (0, 2, 2), (1, 1, 1), (2, None, None)],
)
@mark.parametrize("error_msg_invalid", ["Pruning level must be 0, 1, or 2"])
@mark.parametrize(
    "error_msg_strict", ["Range overlap not registered due to strict pruning policy"]
)
def test_nonduplicate_range_add_with_pruning_Tail(
    centred_range_stream,
    test_pos,
    overlapping_range,
    pruning_level,
    expected_ext_count,
    expected_int_count,
    error_msg_invalid,
    error_msg_strict,
):
    """
    If the pruning policy is to "replant" (`pruning_level` = 0) then a range whose
    "Tail" (T) is overlapped by another range being added will be truncated (if the tail is
    overlapped, by incrementing a `tail_mark` on the internal Range stored).

    Vary the levels of pruning, check the results are as expected when adding an
    overlapping range, and catch the ValueError if the pruning mode is strict.

    The range `[3,7)` overlaps "Head To Tail" (HTT) with the range `[0,11)`, so
    it is expected that the counts of ranges in the RangeDict entry in the internal
    `_ranges` RangeDict should differ for the pruning policies of "replant" and "burn"
    (pruning_level 0 and 1 respectively). Even though there is no remaining range
    left after trimming it, the entry should remain when `pruning_level` is 0.
    """
    centred_range_stream.pruning_level = pruning_level
    if pruning_level in range(2):
        # 0 = replant, 1 = burn
        centred_range_stream.add(overlapping_range)
        assert len(centred_range_stream._ranges) == expected_int_count
        assert len(centred_range_stream.ranges) == expected_ext_count
    else:
        # 2 = strict, anything else is invalid
        error_msg = error_msg_strict if pruning_level == 2 else error_msg_invalid
        with raises(ValueError, match=error_msg):
            centred_range_stream.add(overlapping_range)


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
    """
    empty_range_stream._length = None
    with raises(AttributeError, match=error_msg):
        empty_range_stream.total_range


@mark.parametrize("error_msg", ["Cannot use total_range before setting _length"])
def test_total_range_sabotage_length(empty_range_stream, error_msg):
    """
    RangeStream class's `total_range` property should not work if the _length
    was somehow altered (not possible to access before initialisation).
    """
    empty_range_stream._length = None
    with raises(AttributeError, match=error_msg):
        empty_range_stream.total_range


@mark.parametrize("error_msg", ["Cannot get active range response.*no active range.*"])
def test_empty_stream_tell_init(empty_range_stream, error_msg):
    with raises(ValueError, match=error_msg):
        empty_range_stream.tell()
