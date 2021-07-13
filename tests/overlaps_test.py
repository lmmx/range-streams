from pytest import mark, raises
from ranges import Range

from range_streams.overlaps import get_range_containing, handle_overlap
from range_streams.range_utils import (
    most_recent_range,
    ranges_in_reg_order,
    response_ranges_in_reg_order,
)

from .range_stream_core_test import (
    centred_range_stream,
    empty_range_stream,
    full_range_stream,
    make_range_stream,
)


@mark.parametrize("pruning_level,exp_final_whence", [(0, 1), (1, 1)])
@mark.parametrize("exp_init_whence,overlapping_range", [(0, Range(2, 5))])
@mark.parametrize("pre_pos_in", [[(2, False), (3, True), (5, True), (6, True)]])
@mark.parametrize("post_pos", [[2, 3, 5, 6]])
@mark.parametrize("is_in_post", [True])
def test_add_overlap_head(
    centred_range_stream,
    pruning_level,
    exp_init_whence,
    exp_final_whence,
    overlapping_range,
    pre_pos_in,
    post_pos,
    is_in_post,
):
    """
    Overlapping range [2,5) at the 'head' of [3,7) with intersection length 2
    of total range length 3. Test whether various positions are in or not in the
    internal RangeDict, before and after handling the overlapping range.
    Note: assumed the stream is initialised with (default) pruning level 0 (replant).

    This used to test `handle_overlap` but was then rebuilt for `RangeStream.add`
    since that isn't a principle handler any more...
    """
    initial_whence = centred_range_stream.overlap_whence(overlapping_range)
    assert initial_whence == exp_init_whence
    for pre_position, is_in_pre in pre_pos_in:
        check_pos_in_pre = pre_position in centred_range_stream._ranges
        assert check_pos_in_pre is is_in_pre
    centred_range_stream.add(byte_range=overlapping_range)
    final_whence = centred_range_stream.overlap_whence(overlapping_range)
    assert final_whence is exp_final_whence  # after handling, no overlap is detected
    for post_position in post_pos:
        check_pos_in_post = post_position in centred_range_stream._ranges
        assert check_pos_in_post is is_in_post


@mark.parametrize("pruning_level", [0, 1])
@mark.parametrize("overlapping_range", [Range(2, 5)])
def test_handle_overlap_int_ext_rngdict_Head(
    centred_range_stream,
    pruning_level,
    overlapping_range,
):
    """
    This function tests `handle_overlap` in isolation, ensuring it does not modify
    [in-place] any key in `ranges` when `pruning_level` is 0 ("replant") nor
    the value of the RangeResponse range nor the internal `_ranges` Range keys.

    Note: it does not check that the "burnt" range is deleted, only that there is no
    mismatch between keys and values. Range burning is tested separately.

    Overlapping range [2,5) at the 'head' of [3,7) with intersection length 2
    of total range length 3. Test whether `handle_overlap` changes the internal and
    external RangeDict in the expected way after handling the overlapping range.
    Note: assumed the stream is initialised with (default) pruning level 0 (replant).
    """
    centred_range_stream.pruning_level = pruning_level
    centred_range_stream.handle_overlap(rng=overlapping_range)
    ext_count_changed, int_count_changed = count_rangedict_mutation(
        centred_range_stream
    )
    assert int_count_changed == 0
    assert ext_count_changed == 0  # re-requested if replant, deleted if burn


def count_rangedict_mutation(stream):
    ext_count_changed = 0
    int_count_changed = 0
    for i, rngdict in enumerate([stream.ranges, stream._ranges]):
        for k, v in rngdict.items():
            range_key = k[0].ranges()[0]
            range_value = v.request.range
            if range_key != range_value:
                if i == 0:
                    ext_count_changed += 1
                else:
                    int_count_changed += 1
    return ext_count_changed, int_count_changed


@mark.parametrize("pruning_level,expected", [(0, 1), (1, 0)])
@mark.parametrize("start,stop", [(2, 5)])
@mark.parametrize("overlapping_range", [Range(3, 7)])
def test_handle_overlap_int_ext_rngdict_Tail(
    pruning_level,
    start,
    stop,
    expected,
    overlapping_range,
):
    """
    This function tests `handle_overlap` in isolation, ensuring it modifies [in-place]
    only the value of a key in `ranges` when `pruning_level` is 0 ("replant") and not
    the value of the RangeResponse range nor the internal `_ranges` Range keys.

    Overlapping range [3,7) at the 'tail' of [2,5) with intersection length 2
    of total range length 3. Test whether `handle_overlap` changes the internal and
    external RangeDict in the expected way after handling the overlapping range.
    Note: assumed the stream is initialised with (default) pruning level 0 (replant).
    """
    stream = make_range_stream(start, stop)
    stream.pruning_level = pruning_level
    stream.handle_overlap(rng=overlapping_range)
    ext_count_changed, int_count_changed = count_rangedict_mutation(stream)
    assert int_count_changed == 0
    assert ext_count_changed == expected  # tail marked if replant, deleted if burn
    if pruning_level == 1:
        assert stream._ranges.isempty()
    else:
        init_rng = Range(start, stop)
        resized_rng = Range(start, overlapping_range.start)
        internal_rng_list = ranges_in_reg_order(stream._ranges)
        internal_resp_rng_list = response_ranges_in_reg_order(stream._ranges)
        assert init_rng in internal_rng_list
        assert init_rng in internal_resp_rng_list
        external_rng_list = ranges_in_reg_order(stream.ranges)
        external_resp_rng_list = response_ranges_in_reg_order(stream.ranges)
        # The external range list (i.e. keys of `ranges`) should contain a trimmed
        # version of the overlapped range: [2,5) becomes [2,3) when [3,7) is handled
        assert init_rng not in external_rng_list
        assert resized_rng in external_rng_list
        assert init_rng in external_resp_rng_list


@mark.parametrize("pos,disjoint_range,expected", [(4, Range(0, 1), Range(3, 7))])
def test_range_containing(centred_range_stream, pos, disjoint_range, expected):
    """
    Position 4 in the range [3,7) should identify the range. Also add
    a disjoint range to give full coverage of the generator expression condition.
    """
    centred_range_stream.add(disjoint_range)
    rng = get_range_containing(rng_dict=centred_range_stream.ranges, position=pos)
    assert rng == expected


@mark.parametrize("error_msg", ["No range containing position.*in rng_dict=.*"])
@mark.parametrize("pos", [8])
def test_range_not_containing(centred_range_stream, pos, error_msg):
    """
    The centred range [3,7) does not contain the position 8, so requesting the
    range in the RangeStream made of only this range should fail, with an error.
    """
    with raises(ValueError, match=error_msg):
        get_range_containing(rng_dict=centred_range_stream.ranges, position=pos)


@mark.parametrize("overlapping_range,expected", [(Range(5, 8), 2)])
def test_overlap_tail(centred_range_stream, overlapping_range, expected):
    """
    Overlapping range [5,9) at the 'tail' of [3,7) with intersection length 2
    of total range length 4.  The overlap handler should "bite" off the tail of
    (i.e. trim) the pre-existing range, such that there is no longer an
    overlap detected by `overlap_whence`.
    """
    initial_whence = centred_range_stream.overlap_whence(overlapping_range)
    assert initial_whence == expected
    centred_range_stream.handle_overlap(rng=overlapping_range, internal=False)
    final_whence = centred_range_stream.overlap_whence(overlapping_range)
    assert final_whence is None  # After handling, no overlap is detected


# Edge cases: handling non-overlapping ranges


@mark.parametrize("error_msg", ["Range overlap not detected as the range is empty"])
@mark.parametrize("empty_range", [Range(0, 0)])
def test_no_overlap_empty_range(full_range_stream, empty_range, error_msg):
    """
    The full range [0,11) cannot overlap with the empty range [0,0) because
    (trivially) the empty range has no possibly overlapping ranges.
    """
    with raises(ValueError, match=error_msg):
        handle_overlap(stream=full_range_stream, rng=empty_range, internal=False)


@mark.parametrize("error_msg", ["Range overlap not detected at termini.*"])
@mark.parametrize("nonoverlapping_range", [Range(0, 5)])
def test_no_overlap_empty_range_stream(
    empty_range_stream, nonoverlapping_range, error_msg
):
    """
    Non-overlapping range [0,5) cannot overlap with the empty range [0,0)
    because (trivially) the empty range has no possible overlapping ranges.
    """
    with raises(ValueError, match=error_msg):
        handle_overlap(
            stream=empty_range_stream, rng=nonoverlapping_range, internal=False
        )


@mark.parametrize("initial_ranges", [[(2, 4), (6, 9)]])
@mark.parametrize("overlapping_range", [Range(3, 7)])
def test_partial_overlap_multiple_ranges(
    empty_range_stream, initial_ranges, overlapping_range
):
    """
    Partial overlap with termini of the centred range [3,7) covered on multiple
    ranges (both termini are contained) but `in` does not report True as the
    entirety of this interval is not within the initial ranges: specifically
    because these ranges [2,4) and [6,9) are not contiguous.
    """
    stream = empty_range_stream
    for rng_start, rng_end in initial_ranges:
        stream.add(byte_range=Range(rng_start, rng_end))
    spanning_rng_pre = stream.spanning_range
    handle_overlap(stream=stream, rng=overlapping_range, internal=False)
    spanning_rng_post = stream.spanning_range
    assert spanning_rng_pre == spanning_rng_post
    internal_rng_list = ranges_in_reg_order(stream._ranges)
    external_rng_list = ranges_in_reg_order(stream.ranges)
    assert internal_rng_list[0] > external_rng_list[0]
    assert internal_rng_list[1] == external_rng_list[1]
    stream.add(overlapping_range)
    external_rng_list = ranges_in_reg_order(stream.ranges)
    assert overlapping_range in external_rng_list
    for init_rng in initial_ranges:
        assert init_rng not in external_rng_list
    assert len(external_rng_list) == 3
