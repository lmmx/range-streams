from __future__ import annotations

from pytest import fixture, mark, raises
from ranges import Range

from range_streams.codecs import PngStream

from .data import EXAMPLE_PNG_URL, EXAMPLE_SEMITRANSPARENT_PNG_URL


@fixture(scope="session")
def example_png_stream():
    return PngStream(url=EXAMPLE_PNG_URL)


@fixture(scope="session")
def example_semitransp_png_stream():
    return PngStream(url=EXAMPLE_SEMITRANSPARENT_PNG_URL)


@mark.parametrize("expected", [276])
def test_png_total_bytes(example_png_stream, expected):
    assert example_png_stream.total_bytes == expected


@mark.parametrize("expected", [1])
def test_png_channels_indirect(example_png_stream, expected):
    assert example_png_stream.data.IHDR.channel_count == expected


@mark.parametrize("expected", [3])
def test_png_channels_direct(example_png_stream, expected):
    assert example_png_stream.channel_count_as_direct == expected


@mark.parametrize("expected", [5124])
def test_semitransp_png_total_bytes(example_semitransp_png_stream, expected):
    assert example_semitransp_png_stream.total_bytes == expected


@mark.parametrize("expected", [4])
def test_semitransp_png_channels(example_semitransp_png_stream, expected):
    assert example_semitransp_png_stream.data.IHDR.channel_count == expected


@mark.parametrize("expected", ["IHDR gAMA cHRM PLTE bKGD tIME IDAT tEXt IEND".split()])
def test_png_chunks(example_png_stream, expected):
    assert list(example_png_stream.chunks) == expected


@mark.parametrize("expected", ["IHDR zTXt iCCP bKGD pHYs tIME tEXt IDAT IEND".split()])
def test_semitransp_png_chunks(example_semitransp_png_stream, expected):
    assert list(example_semitransp_png_stream.chunks) == expected


@mark.parametrize("expected", [(40000)])
def test_semitransp_png_chunks(example_semitransp_png_stream, expected):
    """
    Method should be self-testing but do so explicitly here to ensure
    the length value being checked against remains calculated correctly.
    """
    assert len(example_semitransp_png_stream.get_idat_data()) == expected
