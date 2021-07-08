import httpx
from pytest import fixture, mark
from ranges import Range

from range_streams.range_request import RangeRequest

from .data import example_url


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
