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


@mark.parametrize("entries,start_c,start_e", [(1, 103, 165)])
def test_zip_cd_meta(entries, start_c, start_e):
    stream = ZipStream(url=EXAMPLE_ZIP_URL)
    stream.check_end_of_central_dir_rec()
    assert stream.data.CTRL_DIR_REC.entry_count == entries
    assert stream.data.CTRL_DIR_REC.start_pos == start_c
    assert stream.data.E_O_CTRL_DIR_REC.start_pos == start_e


@mark.parametrize("expected", [([b"example_text_file.txt"])])
def test_zip_central_dir_unpack_files(example_zip_stream, expected):
    f = example_zip_stream.get_central_dir_files()
    f_prop = example_zip_stream.file_list
    assert [fn[0] for fn in f] == expected
    assert f_prop == expected
