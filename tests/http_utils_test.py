from pytest import mark
from ranges import Range

from range_streams.http_utils import byte_range_from_range_obj, range_header


@mark.parametrize("start", [0])
@mark.parametrize("stop,expected", [(0, "-0"), (1, "0-0"), (11, "0-10")])
def test_byte_range_to_string(start, stop, expected):
    rng = Range(start, stop)
    assert byte_range_from_range_obj(rng) == expected


@mark.parametrize("start", [0])
@mark.parametrize(
    "stop,expected",
    [
        (stop, {"range": f"bytes={byte_range_str}"})
        for stop, byte_range_str in [
            (0, "-0"),
            (1, "0-0"),
            (11, "0-10"),
        ]
    ],
)
def test_range_header_dict(start, stop, expected):
    rng = Range(start, stop)
    assert range_header(rng) == expected
