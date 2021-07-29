from io import SEEK_END, SEEK_SET

from pytest import fixture, mark, raises
from ranges import Range

from range_streams.response import RangeResponse

from .data import EXAMPLE_FILE_LENGTH
from .range_stream_core_test import empty_range_stream
from .request_test import example_request, make_request


@fixture
def example_response(empty_range_stream, example_request):
    rng = RangeResponse(stream=empty_range_stream, range_request=example_request)
    return rng


@fixture
def full_response(empty_range_stream):
    req = make_request(0, empty_range_stream.total_bytes)
    rng = RangeResponse(stream=empty_range_stream, range_request=req)
    return rng


def test_response(example_response):
    assert isinstance(example_response, RangeResponse)


def test_response_repr(example_response):
    print(f"{example_response!r}")
    assert f"{example_response!r}" == (
        "RangeResponse ⠶ [0, 1) @ 'example_text_file.txt' from github.com"
    )


def test_response_client(example_response, example_request):
    assert example_response.client is example_request.client


def test_response_url(example_response, example_request):
    assert example_response.url is example_request.url


def test_response_name(example_response, empty_range_stream):
    assert example_response.name is empty_range_stream.name


@mark.parametrize("read_size,expected", [(0, 0), (1, 1), (None, 1)])
def test_response_read_tell(example_response, read_size, expected):
    example_response.read(size=read_size)
    assert example_response.tell() == expected


@mark.parametrize("read_size", [100])
def test_response_read_overshoot(example_response, read_size):
    "Hit the StopIteration to cover the `_load_until` break clause"
    example_response.read(size=read_size)


@mark.parametrize(
    "seek,whence,expected",
    [
        (0, SEEK_SET, 0),
        (1, SEEK_SET, 1),
        (0, SEEK_END, 1),
        (-1, SEEK_END, 0),
    ],
)
def test_example_response_seek_tell(example_response, seek, whence, expected):
    example_response.seek(position=seek, whence=whence)
    assert example_response.tell() == expected


@mark.parametrize(
    "seek,whence,expected",
    [
        (0, SEEK_SET, 0),
        (1, SEEK_SET, 1),
        (4, SEEK_SET, 4),
        (0, SEEK_END, 11),
        (-1, SEEK_END, 10),
        (-4, SEEK_END, 7),
    ],
)
def test_full_response_seek_tell(seek, whence, expected):
    req = make_request(0, EXAMPLE_FILE_LENGTH)
    full_response = RangeResponse(stream=empty_range_stream, range_request=req)
    full_response.seek(position=seek, whence=whence)
    assert full_response.tell() == expected


@mark.parametrize("error_msg", [".*no active range.*"])
def test_empty_range_active_range_response_fail(empty_range_stream, error_msg):
    with raises(ValueError, match=error_msg):
        empty_range_stream.active_range_response
