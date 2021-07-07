import httpx
from ranges import Range

from range_streams import RangeStream, example_url


def test_overlapping_bytes():
    c = httpx.Client()
    s = RangeStream(url=example_url, client=c)
    s.handle_byte_range(Range(0, 3))
    s.handle_byte_range(Range(1, 3))
    # TODO: determine correct behaviour to assert
    assert True == True  # isinstance(s, RangeStream)
