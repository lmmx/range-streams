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


@fixture
def full_range_stream():
    "A RangeStream covering the full [0,11) file range."
    c = httpx.Client()
    s = RangeStream(byte_range=Range(0, example_file_length), url=example_url, client=c)
    return s


@fixture
def centred_range_stream():
    "A RangeStream covering the central range [3,7) of the full [0,11) file range."
    c = httpx.Client()
    s = RangeStream(byte_range=Range(3, 7), url=example_url, client=c)
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


def first_rngdict_key(rangestream, internal=True):
    rngdict = rangestream._ranges if internal else rangestream.ranges
    return next(k for k, v in rngdict.items())[0].ranges()[0]


def first_rngdict_key_int_ext_termini(rangestream):
    return [
        (rng.start, rng.end)
        for rng in [first_rngdict_key(rangestream, internal=i) for i in (True, False)]
    ]


def test_range_update(full_range_stream):
    int_termini, ext_termini = first_rngdict_key_int_ext_termini(full_range_stream)
    assert int_termini == (0, 11)
    assert ext_termini == (0, 11)
    full_range_stream.read(4)
    int_termini, ext_termini = first_rngdict_key_int_ext_termini(full_range_stream)
    assert int_termini == (0, 11)
    assert ext_termini == (4, 11)


def test_range_stream_repr(full_range_stream):
    assert f"{full_range_stream!r}" == (
        "RangeStream ⠶ [0, 11) @@ 'example_text_file.txt' from github.com"
    )
