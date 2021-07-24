from __future__ import annotations

from pytest import fixture, mark, raises

from range_streams.codecs import ZipStream

from .data import EXAMPLE_ZIP_URL


@fixture
def example_zip_stream():
    return ZipStream(url=EXAMPLE_ZIP_URL)


@mark.parametrize("expected", [187])
def test_zip_total_bytes(example_zip_stream, expected):
    assert example_zip_stream.total_bytes == expected


@mark.parametrize("expected", [103])
def test_zip_central_dir_bytes(example_zip_stream, expected):
    central_dir_bytes = example_zip_stream.get_central_dir_bytes()
    assert len(central_dir_bytes) == expected


@mark.parametrize("expected", [None])
def test_zip_central_dir_unpack(example_zip_stream, expected):
    central_dir_bytes = example_zip_stream.get_central_dir_bytes()
    # struct.unpack(example_zip_stream.CTRL_DIR_REC.struct, central_dir_bytes)
