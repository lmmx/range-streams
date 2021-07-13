from copy import deepcopy

from pytest import fixture, mark, raises
from ranges import Range

from range_streams.range_utils import (
    ext2int,
    most_recent_range,
    range_len,
    range_max,
    range_min,
    range_span,
    range_termini,
    ranges_in_reg_order,
    response_ranges_in_reg_order,
    validate_range,
)

from .range_stream_core_test import (
    centred_range_stream,
    empty_range_stream,
    full_range_stream,
)

termini_test_triples = [(0, 3, (0, 2)), (1, 4, (1, 3))]


@mark.parametrize("start,stop,expected", termini_test_triples)
def test_range_termini(start, stop, expected):
    rng = Range(start, stop)
    assert range_termini(rng) == expected


@mark.parametrize("start,stop,expected", termini_test_triples)
def test_range_min(start, stop, expected):
    min_expected, _ = expected
    rng = Range(start, stop)
    assert range_min(rng) == min_expected


@mark.parametrize("start,stop,expected", termini_test_triples)
def test_range_max(start, stop, expected):
    _, max_expected = expected
    rng = Range(start, stop)
    assert range_max(rng) == max_expected


@mark.parametrize("start,stop,_", termini_test_triples)
def test_range_len(start, stop, _):
    rng = Range(start, stop)
    rlen = (stop - start) - 1
    assert range_len(rng) == rlen


@mark.parametrize("start,stop,expected", termini_test_triples)
def test_range_min_terminus(start, stop, expected):
    rng = Range(start, stop)
    min_terminus, _ = expected
    assert range_termini(rng)[0] == min_terminus


@mark.parametrize("start,stop,expected", termini_test_triples)
def test_range_max_terminus(start, stop, expected):
    rng = Range(start, stop)
    _, max_terminus = expected
    assert range_termini(rng)[1] == max_terminus


@mark.parametrize("rng", [(1, 3), Range(1, 3)])
def test_validate_range(rng):
    expected = Range(rng[0], rng[1]) if isinstance(rng, tuple) else rng
    assert validate_range(rng) == expected


@mark.parametrize(
    "first_rng,last_rng,span_rng",
    [
        (Range(0, 2), Range(9, 10), Range(0, 10)),
        (Range(3, 5), Range(4, 6), Range(3, 6)),
        (Range(9, 10), Range(0, 2), Range(0, 10)),
        (Range(4, 6), Range(3, 5), Range(3, 6)),
    ],
)
def test_range_span(first_rng, last_rng, span_rng):
    assert range_span([first_rng, last_rng]) == span_rng


## Handling the edge case of incorrect types for ranges (dynamically typed)


@mark.parametrize(
    "error_msg", ["Ranges must be discrete: use integers for start and end"]
)
@mark.parametrize("float_range", [Range(1.5, 4.5)])
def test_validate_float_range(float_range, error_msg):
    with raises(TypeError, match=error_msg):
        validate_range(float_range)


@mark.parametrize(
    "error_msg",
    [
        "byte_range=.* must be a Range from the python-ranges package or an integer 2-tuple"
    ],
)
@mark.parametrize("list_range", [(1, 2.5), (1, 2, 3), [0, 3]])
def test_validate_list_range(list_range, error_msg):
    with raises(TypeError, match=error_msg):
        validate_range(list_range)


## Handling the edge case of empty ranges


@fixture
def empty_range():
    return Range(0, 0)


@mark.parametrize("error_msg", ["Empty range has no termini"])
def test_empty_range_termini(empty_range, error_msg):
    with raises(ValueError, match=error_msg):
        range_termini(empty_range)


@mark.parametrize("error_msg", ["Empty range has no minimum"])
def test_empty_range_min(empty_range, error_msg):
    with raises(ValueError, match=error_msg):
        range_min(empty_range)


@mark.parametrize("error_msg", ["Empty range has no maximum"])
def test_empty_range_max(empty_range, error_msg):
    with raises(ValueError, match=error_msg):
        range_max(empty_range)


@mark.parametrize("error_msg", ["Range is empty"])
def test_empty_range_validate(empty_range, error_msg):
    with raises(ValueError, match=error_msg):
        validate_range(empty_range, allow_empty=False)


def test_most_recent_range_empty(empty_range_stream):
    assert most_recent_range(empty_range_stream) is None


@mark.parametrize("expected", [Range(0, 11)])
def test_most_recent_range_full(full_range_stream, expected):
    assert most_recent_range(full_range_stream) == expected
