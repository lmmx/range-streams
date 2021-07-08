import httpx
from pytest import fixture
from ranges import Range

from range_streams import RangeStream, example_url


@fixture
def empty_range_stream():
    c = httpx.Client()
    s = RangeStream(url=example_url, client=c)
    return s


def test_empty_range(empty_range_stream):
    assert isinstance(empty_range_stream, RangeStream)


def make_range_stream(start, stop):
    c = httpx.Client()
    s = RangeStream(range=Range(start, stop), url=example_url, client=c)
    return s


@fixture(params=[(0, 1), (0, 2), (0, 3)])
def test_range(start, stop):
    s = make_range_stream(start, stop)
    assert s._active_range == Range(start, stop)


def test_overlapping_ranges(empty_range_stream):
    s = empty_range_stream
    s.handle_byte_range(Range(0, 3))
    s.handle_byte_range(Range(1, 3))
    # TODO: determine correct behaviour to assert
    assert isinstance(s, RangeStream)
