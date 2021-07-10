from pytest import fixture, mark, raises
from ranges import Range

from range_streams.overlaps import get_range_containing, handle_overlap, overlap_whence

from .range_stream_core_test import (
    centred_range_stream,
    empty_range_stream,
    full_range_stream,
)


@mark.parametrize("overlapping_range,expected", [(Range(2, 5), 0)])
def test_overlap_head(centred_range_stream, overlapping_range, expected):
    """
    Overlapping range [2,5) at the 'head' of [3,7) with intersection length 2
    of total range length 3.
    """
    initial_whence = centred_range_stream.overlap_whence(overlapping_range)
    assert initial_whence == expected
    centred_range_stream.handle_overlap(rng=overlapping_range)
    final_whence = centred_range_stream.overlap_whence(overlapping_range)
    assert final_whence is None  # after handling, no overlap is detected


@mark.parametrize("pos,expected", [(4, Range(3, 7))])
def test_range_containing(centred_range_stream, pos, expected):
    """
    Position 4 in the range [3,7) should identify the range.
    """
    rng = get_range_containing(rng_dict=centred_range_stream.ranges, position=pos)
    assert rng == expected


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
    centred_range_stream.handle_overlap(rng=overlapping_range)
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
        handle_overlap(ranges=full_range_stream._ranges, rng=empty_range)


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
        handle_overlap(ranges=empty_range_stream._ranges, rng=nonoverlapping_range)


@mark.parametrize("error_msg", ["Partially contained on multiple ranges"])
@mark.parametrize("initial_ranges", [[(2, 4), (6, 9)]])
@mark.parametrize("overlapping_range", [Range(3, 7)])
def test_partial_overlap_multiple_ranges(
    empty_range_stream, initial_ranges, overlapping_range, error_msg
):
    """
    Partial overlap with termini of the centred range [3,7) covered on multiple
    ranges (both termini are contained) but `in` does not report True as the
    entirety of this interval is not within the initial ranges: specifically
    because these ranges [2,4) and [6,9) are not contiguous.
    """
    with raises(NotImplementedError, match=error_msg):
        s = empty_range_stream
        for rng_start, rng_end in initial_ranges:
            s.handle_byte_range(byte_range=Range(rng_start, rng_end))
        handle_overlap(ranges=empty_range_stream._ranges, rng=overlapping_range)
