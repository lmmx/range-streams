from pytest import fixture, mark, raises
from ranges import Range

from range_streams.range_utils import (
    range_len,
    range_max,
    range_min,
    range_span,
    range_termini,
    validate_range,
)

termini_test_triples = [(0, 3, (0, 2)), (1, 4, (1, 3))]


@mark.parametrize("start,stop,expected", termini_test_triples)
def test_range_termini(start, stop, expected):
    r = Range(start, stop)
    assert range_termini(r) == expected


@mark.parametrize("start,stop,expected", termini_test_triples)
def test_range_min(start, stop, expected):
    min_expected, _ = expected
    r = Range(start, stop)
    assert range_min(r) == min_expected


@mark.parametrize("start,stop,expected", termini_test_triples)
def test_range_max(start, stop, expected):
    _, max_expected = expected
    r = Range(start, stop)
    assert range_max(r) == max_expected


@mark.parametrize("start,stop,_", termini_test_triples)
def test_range_len(start, stop, _):
    r = Range(start, stop)
    l = (stop - start) - 1
    assert range_len(r) == l


@mark.parametrize("start,stop,expected", termini_test_triples)
def test_range_min_terminus(start, stop, expected):
    r = Range(start, stop)
    min_terminus, _ = expected
    assert range_termini(r)[0] == min_terminus


@mark.parametrize("start,stop,expected", termini_test_triples)
def test_range_max_terminus(start, stop, expected):
    r = Range(start, stop)
    _, max_terminus = expected
    assert range_termini(r)[1] == max_terminus


@mark.parametrize("rng", [(1, 3), Range(1, 3)])
def test_validate_range(rng):
    tup_rng = Range(rng[0], rng[1]) if isinstance(rng, tuple) else rng
    assert validate_range(rng) is tup_rng


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
