import httpx
from pytest import fixture, mark, raises
from ranges import Range

from range_streams.request import RangeRequest

from .data import EXAMPLE_FILE_LENGTH, EXAMPLE_URL
from .share import client


def make_request(start, stop):
    rng = RangeRequest(
        byte_range=Range(start, stop),
        url=EXAMPLE_URL,
        client=client,
    )
    return rng


@mark.parametrize(
    "start,stop,expected", [(0, i + 1, {"range": f"bytes=0-{i}"}) for i in range(3)]
)
def test_range_headers(start, stop, expected):
    rng = make_request(start, stop)
    assert rng.range_header == expected


@fixture
def example_request():
    start, stop = 0, 1
    return make_request(start, stop)


def test_response_closing(example_request):
    assert example_request.response.is_closed is False
    example_request.close()
    assert example_request.response.is_closed is True
    example_request.close()


def test_request_iter_raw(example_request):
    iterator = example_request.iter_raw()
    byte = next(iterator)
    assert byte == b"P"


@mark.parametrize("start", [0])
@mark.parametrize(
    "stop,expected",
    [
        (0, {"range": f"bytes=0-"}),
        (1, {"range": f"bytes=0-1"}),
    ],
)
def test_range_length(start, stop, expected):
    rng = make_request(start, stop)
    assert rng.total_content_length == EXAMPLE_FILE_LENGTH


@mark.parametrize("error_msg", ["Response was missing 'content-range' header.*"])
def test_range_header_missing(example_request, error_msg):
    del example_request.response.headers["content-range"]
    with raises(KeyError, match=error_msg):
        example_request.content_range_header()
