import httpx
from pytest import fixture, mark, raises
from ranges import Range

from range_streams.range_request import RangeRequest

from .data import example_file_length, example_url


def make_range_request(start, stop):
    c = httpx.Client()
    r = RangeRequest(byte_range=Range(start, stop), url=example_url, client=c)
    return r


@mark.parametrize(
    "start,stop,expected", [(0, i + 1, {"range": f"bytes=0-{i}"}) for i in range(3)]
)
def test_range_headers(start, stop, expected):
    r = make_range_request(start, stop)
    assert r.range_header == expected


@fixture
def example_range_request():
    start, stop = 0, 1
    return make_range_request(start, stop)


def test_range_response_closing(example_range_request):
    assert not example_range_request.response.is_closed
    example_range_request.close()
    assert example_range_request.response.is_closed


def test_range_request_iter_raw(example_range_request):
    iterator = example_range_request.iter_raw()
    b = next(iterator)
    assert b == b"P"


@mark.parametrize("start", [0])
@mark.parametrize("stop,expected", [(i, {"range": f"bytes=0-{i}"}) for i in range(2)])
def test_range_length(start, stop, expected):
    r = make_range_request(start, stop)
    assert r.total_content_length == example_file_length


@mark.parametrize("error_msg", ["Response was missing 'content-range' header.*"])
def test_range_header_missing(example_range_request, error_msg):
    del example_range_request.response.headers["content-range"]
    with raises(KeyError, match=error_msg):
        example_range_request.content_range_header()
