from io import SEEK_END, SEEK_SET

import httpx
from pytest import fixture, mark, raises
from ranges import Range

from range_streams.request import RangeRequest
from range_streams.response import RangeResponse
from range_streams.stream import RangeStream

from .data import EXAMPLE_FILE_LENGTH, EXAMPLE_URL

# from .request_test import example_request, make_request


client = httpx.Client()


@fixture(scope="session")
def empty_range_stream():
    """
    By default, not passing the `byte_range` param to `RangeStream` will give the
    empty `Range(0,0)`. Create a fixture as a "starting point" for other tests.

    Duplicate of the one in :mod:`range_stream_core_test` (fresh client)
    """
    return RangeStream(url=EXAMPLE_URL, client=client)


def make_request(start, stop):
    """
    Duplicate of the one in :mod:`request_test` (fresh client)
    """
    rng = RangeRequest(
        byte_range=Range(start, stop),
        url=EXAMPLE_URL,
        client=client,
    )
    return rng


@fixture
def example_request():
    start, stop = 0, 1
    return make_request(start, stop)


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
        "RangeResponse ⠶ [0, 1) @ 'example_text_file.txt' from raw.githubusercontent.com"
    )


# def test_response_client(example_response, example_request):
#    assert example_response.client is example_request.client


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
def test_full_response_seek_tell(seek, whence, expected, empty_range_stream):
    req = make_request(0, EXAMPLE_FILE_LENGTH)
    full_response = RangeResponse(stream=empty_range_stream, range_request=req)
    full_response.seek(position=seek, whence=whence)
    assert full_response.tell() == expected


@mark.parametrize("error_msg", [".*no active range.*"])
def test_empty_range_active_range_response_fail(empty_range_stream, error_msg):
    with raises(ValueError, match=error_msg):
        empty_range_stream.active_range_response
