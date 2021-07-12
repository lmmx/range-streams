import httpx
from pytest import fixture, mark
from ranges import Range

from range_streams import RangeStream

from .data import EXAMPLE_FILE_LENGTH, EXAMPLE_URL


@fixture
def empty_range_stream():
    """
    By default, not passing the `byte_range` param to `RangeStream` will give the
    empty `Range(0,0)`. Create a fixture as a "starting point" for other tests.
    """
    client = httpx.Client()
    return RangeStream(url=EXAMPLE_URL, client=client)


@fixture
def full_range_stream():
    "A RangeStream covering the full [0,11) file range."
    client = httpx.Client()
    rng = Range(0, EXAMPLE_FILE_LENGTH)
    return RangeStream(byte_range=rng, url=EXAMPLE_URL, client=client)


@fixture
def centred_range_stream():
    "A RangeStream covering the central range [3,7) of the full [0,11) file range."
    client = httpx.Client()
    return RangeStream(byte_range=Range(3, 7), url=EXAMPLE_URL, client=client)


def test_empty_range(empty_range_stream):
    assert isinstance(empty_range_stream, RangeStream)


@mark.parametrize("start", [0])
@mark.parametrize("stop", [1, 5, EXAMPLE_FILE_LENGTH])
def test_active_range(start, stop):
    """
    The example file used is 11 bytes long, so this test uses
    1, 5, and all 11 bytes in separate runs, using `parametrize`.
    The `_active_range` attribute is set for all except the
    empty range (where it remains `None` as in the classdef)
    """
    stream = make_range_stream(start, stop)
    assert stream._active_range == Range(start, stop)


@mark.parametrize("start,stop", [(0, 0)])
def test_active_range_empty(start, stop):
    """
    The `_active_range` attribute is set for all except the
    empty range (where it remains `None` as in the classdef)
    so test this assumption.
    """
    stream = make_range_stream(start, stop)
    assert stream._active_range is None


def test_empty_range_total_bytes(empty_range_stream):
    assert empty_range_stream.total_bytes == EXAMPLE_FILE_LENGTH


def make_range_stream(start, stop):
    client = httpx.Client()
    return RangeStream(byte_range=Range(start, stop), url=EXAMPLE_URL, client=client)


@fixture(params=[(0, 1), (0, 2), (0, 3)])
def test_range(start, stop):
    stream = make_range_stream(start, stop)
    assert stream._active_range == Range(start, stop)


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


def test_empty_range_stream_empty(empty_range_stream):
    assert empty_range_stream.isempty() is True


def test_empty_range_span(empty_range_stream):
    assert empty_range_stream.spanning_range == Range(0, 0)


@mark.parametrize("start,stop", [(0, 4)])
@mark.parametrize("range_pairs", [[(0, 4), (6, 11)], [(2, 3), (5, 6), (8, 9)]])
def test_multiple_range_span(start, stop, range_pairs):
    stream = make_range_stream(start, stop)
    for rng_start, rng_stop in range_pairs:
        stream.add(byte_range=Range(rng_start, rng_stop))
    rng_min, rng_max = range_pairs[0][0], range_pairs[-1][-1]
    assert stream.spanning_range == Range(rng_min, rng_max)


def test_stream_tell_init(full_range_stream):
    assert full_range_stream.tell() == 0


@mark.parametrize("size", [0, 5, EXAMPLE_FILE_LENGTH])
def test_stream_tell_read(full_range_stream, size):
    full_range_stream.read(size=size)
    assert full_range_stream.tell() == size


@mark.parametrize("pos", [0, 5, EXAMPLE_FILE_LENGTH])
def test_stream_seek_tell(full_range_stream, pos):
    full_range_stream.seek(position=pos)
    assert full_range_stream.tell() == pos


def test_active_range_changes(empty_range_stream):
    assert empty_range_stream._active_range is None
    rng1 = Range(0, 1)
    empty_range_stream.add(rng1)
    assert empty_range_stream._active_range == rng1
    rng2 = Range(4, 6)
    empty_range_stream.add(rng2)
    assert empty_range_stream._active_range == rng2


def test_add_range_no_activate(empty_range_stream):
    assert empty_range_stream._active_range is None
    rng1 = Range(0, 1)
    empty_range_stream.add(rng1, activate=False)
    assert empty_range_stream._active_range is None
    rng2 = Range(4, 6)
    empty_range_stream.add(rng2, activate=False)
    assert empty_range_stream._active_range is None
