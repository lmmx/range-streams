from pytest import fixture, mark, raises
from ranges import Range

from range_streams.overlaps import handle_overlap, overlap_whence

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
    assert final_whence is None  # After handling, no overlap is detected


@mark.parametrize("overlapping_range,expected", [(Range(4, 6), 1)])
def test_overlap_midbody(centred_range_stream, overlapping_range, expected):
    """
    Overlapping range [4,6) at the 'mid-body' of [3,7) with intersection length 2
    of total range length 2.
    """
    initial_whence = centred_range_stream.overlap_whence(overlapping_range)
    assert initial_whence == expected
    centred_range_stream.handle_overlap(rng=overlapping_range)
    final_whence = centred_range_stream.overlap_whence(overlapping_range)
    assert final_whence is None  # After handling, no overlap is detected


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


@mark.parametrize(
    "empty_range, error_msg",
    [(Range(0, 0), "Range overlap not detected as the range is empty")],
)
def test_no_overlap_empty_range(full_range_stream, empty_range, error_msg):
    """
    The full range [0,11) cannot overlap with the empty range [0,0) because
    (trivially) the empty range has no possibly overlapping ranges.
    """
    with raises(ValueError, match=error_msg):
        handle_overlap(ranges=full_range_stream._ranges, rng=empty_range)


@mark.parametrize(
    "nonoverlapping_range, error_msg",
    [(Range(0, 5), "Range overlap not detected at termini.*")],
)
def test_no_overlap_empty_range_stream(
    empty_range_stream, nonoverlapping_range, error_msg
):
    """
    Non-overlapping range [0,5) cannot overlap with the empty range [0,0)
    because (trivially) the empty range has no possible overlapping ranges.
    """
    with raises(ValueError, match=error_msg):
        handle_overlap(ranges=empty_range_stream._ranges, rng=nonoverlapping_range)
