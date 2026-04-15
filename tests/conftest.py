from pytest import fixture
from ranges import Range

from range_streams import RangeStream

from .data import EXAMPLE_FILE_LENGTH, EXAMPLE_URL
from .share import client


@fixture
def empty_range_stream():
    """
    By default, not passing the `byte_range` param to `RangeStream` will give the
    empty `Range(0,0)`. Create a fixture as a "starting point" for other tests.
    """
    return RangeStream(url=EXAMPLE_URL, client=client)


@fixture
def empty_range_stream_fresh():
    """
    As for empty_range_stream, but regenerated on each use, for tests which modify it.
    """
    return RangeStream(url=EXAMPLE_URL, client=client)


@fixture
def full_range_stream():
    "A RangeStream covering the full [0,11) file range."
    rng = Range(0, EXAMPLE_FILE_LENGTH)
    return RangeStream(byte_range=rng, url=EXAMPLE_URL, client=client)


@fixture
def full_range_stream_fresh():
    "As for full_range_stream, but regenerated on each use, for tests which modify it."
    rng = Range(0, EXAMPLE_FILE_LENGTH)
    return RangeStream(byte_range=rng, url=EXAMPLE_URL, client=client)


@fixture
def centred_range_stream():
    "A RangeStream covering the central range [3,7) of the full [0,11) file range."
    return RangeStream(byte_range=Range(3, 7), url=EXAMPLE_URL, client=client)


@fixture
def centred_range_stream_fresh():
    "As for centred_range_stream, but regenerated on each use, for tests which modify it."
    return RangeStream(byte_range=Range(3, 7), url=EXAMPLE_URL, client=client)
