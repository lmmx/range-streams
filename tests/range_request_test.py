import httpx
from pytest import fixture, mark, raises
from ranges import Range

from range_streams.range_request import RangeRequest

from .data import EXAMPLE_FILE_LENGTH, EXAMPLE_URL


def make_range_request(start, stop):
    client = httpx.Client()
    rng = RangeRequest(byte_range=Range(start, stop), url=EXAMPLE_URL, client=client)
    return rng


@mark.parametrize(
    "start,stop,expected", [(0, i + 1, {"range": f"bytes=0-{i}"}) for i in range(3)]
)
def test_range_headers(start, stop, expected):
    rng = make_range_request(start, stop)
    assert rng.range_header == expected


@fixture
def example_range_request():
    start, stop = 0, 1
    return make_range_request(start, stop)


def test_range_response_closing(example_range_request):
    assert example_range_request.response.is_closed is False
    example_range_request.close()
    assert example_range_request.response.is_closed is True
    example_range_request.close()


def test_range_request_iter_raw(example_range_request):
    iterator = example_range_request.iter_raw()
    byte = next(iterator)
    assert byte == b"P"


@mark.parametrize("start", [0])
@mark.parametrize("stop,expected", [(i, {"range": f"bytes=0-{i}"}) for i in range(2)])
def test_range_length(start, stop, expected):
    rng = make_range_request(start, stop)
    assert rng.total_content_length == EXAMPLE_FILE_LENGTH


@mark.parametrize("error_msg", ["Response was missing 'content-range' header.*"])
def test_range_header_missing(example_range_request, error_msg):
    del example_range_request.response.headers["content-range"]
    with raises(KeyError, match=error_msg):
        example_range_request.content_range_header()
