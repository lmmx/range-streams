import httpx
from pytest import fixture, mark
from ranges import Range

from range_streams import RangeStream, example_url


@fixture
def empty_range_stream():
    c = httpx.Client()
    s = RangeStream(url=example_url, client=c)
    return s


def test_empty_range(empty_range_stream):
    assert isinstance(empty_range_stream, RangeStream)


@mark.parametrize("start,stop", [(0, i) for i in (1, 5, 12)])
def test_range(start, stop):
    s = make_range_stream(start, stop)
    assert s._active_range == Range(start, stop)


def test_empty_range_total_bytes(empty_range_stream):
    assert empty_range_stream.total_bytes == 11


def make_range_stream(start, stop):
    c = httpx.Client()
    s = RangeStream(byte_range=Range(start, stop), url=example_url, client=c)
    return s


@fixture(params=[(0, 1), (0, 2), (0, 3)])
def test_range(start, stop):
    s = make_range_stream(start, stop)
    assert s._active_range == Range(start, stop)
