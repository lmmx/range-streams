import httpx
from pytest import fixture, mark
from ranges import Range

from range_streams import RangeStream

from .data import example_file_length, example_url


@fixture
def empty_range_stream():
    """
    By default, not passing the `byte_range` param to `RangeStream` will give the
    empty `Range(0,0)`. Create a fixture as a "starting point" for other tests.
    """
    c = httpx.Client()
    s = RangeStream(url=example_url, client=c)
    return s


def test_empty_range(empty_range_stream):
    assert isinstance(empty_range_stream, RangeStream)


@mark.parametrize("start,stop", [(0, i) for i in (1, 5, example_file_length)])
def test_active_range(start, stop):
    """
    The example file used is 11 bytes long, so this test uses
    1, 5, and all 11 bytes in separate runs, using `parametrize`.
    The `_active_range` attribute is set for all except the
    empty range (where it remains `None` as in the classdef)
    """
    s = make_range_stream(start, stop)
    assert s._active_range == Range(start, stop)


@mark.parametrize("start,stop", [(0, 0)])
def test_active_range_empty(start, stop):
    """
    The `_active_range` attribute is set for all except the
    empty range (where it remains `None` as in the classdef)
    so test this assumption.
    """
    s = make_range_stream(start, stop)
    assert s._active_range is None


def test_empty_range_total_bytes(empty_range_stream):
    assert empty_range_stream.total_bytes == example_file_length


def make_range_stream(start, stop):
    c = httpx.Client()
    s = RangeStream(byte_range=Range(start, stop), url=example_url, client=c)
    return s


@fixture(params=[(0, 1), (0, 2), (0, 3)])
def test_range(start, stop):
    s = make_range_stream(start, stop)
    assert s._active_range == Range(start, stop)
