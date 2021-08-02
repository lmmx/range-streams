import httpx
from pytest import fixture, mark, raises
from ranges import Range

from range_streams import RangeStream

from .data import EXAMPLE_FILE_LENGTH, EXAMPLE_URL
from .range_stream_core_test import empty_range_stream, full_range_stream
from .share import client


@fixture(scope="session")
def monostream():
    """
    By default, not passing the ``byte_range`` param to
    :class:`~range_streams.stream.RangeStream` will give the empty ``Range(0,0)``.
    When ``single_request`` is passed as ``True`` as well, the
    result is a stream with a single range spanning the entire file.

    Create a fixture as a "starting point" for other tests.
    """
    return RangeStream(url=EXAMPLE_URL, client=client, single_request=True)


@fixture
def monostream_fresh():
    """
    As for monostream, but regenerated on each use, for tests which modify it.
    """
    return RangeStream(url=EXAMPLE_URL, client=client, single_request=True)


def test_monostream_init(monostream, full_range_stream):
    assert isinstance(monostream, RangeStream)


def test_monostream_init_same_as_empty_stream(
    monostream, empty_range_stream, full_range_stream
):
    assert repr(monostream.ranges) == repr(empty_range_stream.ranges)
    assert repr(monostream._ranges) == repr(full_range_stream._ranges)
    # Initialised attributes
    assert monostream.url == empty_range_stream.url
    assert monostream.client == empty_range_stream.client
    assert monostream.pruning_level == empty_range_stream.pruning_level
    assert monostream.single_request is not empty_range_stream.single_request
    assert monostream._length_checked is empty_range_stream._length_checked
    assert monostream._active_range is empty_range_stream._active_range
    # Further properties and methods
    arr_err = "Cannot get active range response..no active range"
    with raises(ValueError, match=arr_err):
        monostream.active_range_response
    with raises(ValueError, match=arr_err):
        empty_range_stream.active_range_response
    assert monostream.name == empty_range_stream.name
    assert monostream.spanning_range == empty_range_stream.spanning_range
    assert monostream.total_bytes == empty_range_stream.total_bytes
    assert monostream.total_range == empty_range_stream.total_range
    assert monostream.isempty() == empty_range_stream.isempty()
    with raises(ValueError, match=arr_err):
        assert monostream.tell() == empty_range_stream.tell()
    assert monostream.domain == empty_range_stream.domain


def test_monostream_full_same_as_full_stream(monostream_fresh, full_range_stream):
    # Until this point, `test_monostream_init_same_as_empty_stream` is the case
    monostream_fresh.add(monostream_fresh.total_range)  # Adds windowed range
    assert repr(monostream_fresh.ranges) == repr(full_range_stream.ranges)
    assert repr(monostream_fresh._ranges) == repr(full_range_stream._ranges)
    # Initialised attributes
    assert monostream_fresh.url == full_range_stream.url
    assert monostream_fresh.client == full_range_stream.client
    assert monostream_fresh.pruning_level == full_range_stream.pruning_level
    assert monostream_fresh.single_request is not full_range_stream.single_request
    assert monostream_fresh._length_checked is full_range_stream._length_checked
    assert monostream_fresh._active_range == full_range_stream._active_range
    # Further properties and methods
    assert repr(monostream_fresh.active_range_response) == repr(
        full_range_stream.active_range_response
    )
    assert monostream_fresh.name == full_range_stream.name
    assert monostream_fresh.spanning_range == full_range_stream.spanning_range
    assert monostream_fresh.total_bytes == full_range_stream.total_bytes
    assert monostream_fresh.total_range == full_range_stream.total_range
    assert monostream_fresh.isempty() == full_range_stream.isempty()
    assert monostream_fresh.tell() == full_range_stream.tell()
    assert monostream_fresh.domain == full_range_stream.domain
