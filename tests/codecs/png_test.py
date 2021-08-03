from __future__ import annotations

from pytest import fixture, mark, raises
from ranges import Range

from range_streams.codecs import PngStream

from .data import (
    EXAMPLE_MULTI_IDAT_PNG_URL,
    EXAMPLE_PNG_URL,
    EXAMPLE_SEMITRANSPARENT_PNG_URL,
)


@fixture(scope="session")
def example_png_stream():
    return PngStream(url=EXAMPLE_PNG_URL, single_request=False)


@fixture(scope="session")
def example_semitransp_png_stream():
    return PngStream(url=EXAMPLE_SEMITRANSPARENT_PNG_URL, single_request=False)


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


@mark.parametrize(
    "expected_len,expected_semitransp,expected_transp", [(40000, True, True)]
)
def test_semitransp_png_chunks(
    example_semitransp_png_stream, expected_len, expected_semitransp, expected_transp
):
    """
    Method should be self-testing but do so explicitly here to ensure
    the length value being checked against remains calculated correctly.
    """
    assert len(example_semitransp_png_stream.get_idat_data()) == expected_len
    assert (
        example_semitransp_png_stream.any_semitransparent_idat(nonzero=True)
        == expected_semitransp
    )
    assert (
        example_semitransp_png_stream.any_semitransparent_idat(nonzero=False)
        == expected_transp
    )


@mark.parametrize(
    "expected_len,expected_semitransp,expected_transp", [(921600, False, False)]
)
def test_multi_idat_png_chunk_parse(expected_len, expected_semitransp, expected_transp):
    stream = PngStream(url=EXAMPLE_MULTI_IDAT_PNG_URL, single_request=False)
    idat = stream.get_idat_data()
    assert len(idat) == expected_len
    assert stream.any_semitransparent_idat(nonzero=True) == expected_semitransp
    assert stream.any_semitransparent_idat(nonzero=False) == expected_transp
