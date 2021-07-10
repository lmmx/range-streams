from io import SEEK_END, SEEK_SET

import httpx
from pytest import fixture, mark, raises
from ranges import Range

from range_streams.range_response import RangeResponse

from .data import example_file_length, example_url
from .range_request_test import example_range_request, make_range_request
from .range_stream_core_test import empty_range_stream


@fixture
def example_range_response(empty_range_stream, example_range_request):
    r = RangeResponse(stream=empty_range_stream, range_request=example_range_request)
    return r


@fixture
def full_range_response(empty_range_stream):
    req = make_range_request(0, empty_range_stream.total_bytes)
    r = RangeResponse(stream=empty_range_stream, range_request=example_range_request)
    return r


def test_range_response(example_range_response):
    assert isinstance(example_range_response, RangeResponse)


def test_range_response_client(example_range_response, example_range_request):
    assert example_range_response.client is example_range_request.client


def test_range_response_url(example_range_response, example_range_request):
    assert example_range_response.url is example_range_request.url


def test_range_response_name(example_range_response, empty_range_stream):
    assert example_range_response.name is empty_range_stream.name


@mark.parametrize("read_size,expected", [(0, 0), (1, 1), (None, 1)])
def test_range_response_read_tell(example_range_response, read_size, expected):
    example_range_response.read(size=read_size)
    assert example_range_response.tell() == expected


@mark.parametrize(
    "seek,whence,expected",
    [
        (0, SEEK_SET, 0),
        (1, SEEK_SET, 1),
        (0, SEEK_END, 0),
        (1, SEEK_END, 1),
    ],
)
def test_example_range_response_seek_tell(
    example_range_response, seek, whence, expected
):
    example_range_response.seek(position=seek)
    assert example_range_response.tell() == expected


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
def test_full_range_response_seek_tell(seek, whence, expected):
    req = make_range_request(0, example_file_length)
    full_range_response = RangeResponse(stream=empty_range_stream, range_request=req)
    full_range_response.seek(position=seek, whence=whence)
    assert full_range_response.tell() == expected


@mark.parametrize("error_msg", [".*no active range.*"])
def test_empty_range_active_range_response_fail(empty_range_stream, error_msg):
    with raises(ValueError, match=error_msg):
        empty_range_stream.active_range_response
