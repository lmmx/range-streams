from __future__ import annotations

from pytest import fixture, mark, raises
from ranges import Range

from range_streams.codecs import ZipStream

from .data import EXAMPLE_ZIP_URL


@fixture(scope="session")
def example_zip_stream():
    return ZipStream(url=EXAMPLE_ZIP_URL)


@mark.parametrize("expected", [187])
def test_zip_total_bytes(example_zip_stream, expected):
    assert example_zip_stream.total_bytes == expected


@mark.parametrize("expected", [103])
def test_zip_central_dir_bytes(example_zip_stream, expected):
    central_dir_bytes = example_zip_stream.get_central_dir_bytes()
    assert len(central_dir_bytes) == expected


@mark.parametrize("entries,size,start_c,start_e", [(1, 103, 62, 165)])
def test_zip_cd_meta(entries, size, start_c, start_e):
    stream = ZipStream(url=EXAMPLE_ZIP_URL)
    stream.check_end_of_central_dir_rec()
    assert stream.data.CTRL_DIR_REC.entry_count == entries
    assert stream.data.CTRL_DIR_REC.size == size
    assert stream.data.CTRL_DIR_REC.start_pos == start_c
    stream.add(Range(start_c, start_c + 4))
    b = stream.active_range_response.read()
    assert b == stream.data.CTRL_DIR_REC.start_sig
    assert stream.data.E_O_CTRL_DIR_REC.start_pos == start_e
    assert start_c + size == start_e


@mark.parametrize("expected", [["example_text_file.txt"]])
def test_zip_central_dir_list_files(example_zip_stream, expected):
    assert example_zip_stream.filename_list == expected


@mark.parametrize(
    "fname,fname_len,com_len,size,rng_start,rng_end",
    [("example_text_file.txt", 21, 0, 11, 51, 62)],
)
def test_zipped_file_contents(
    example_zip_stream, fname, fname_len, com_len, size, rng_start, rng_end
):
    zf_l = example_zip_stream.zipped_files
    assert len(zf_l) == 1
    zf = zf_l[0]
    assert zf.filename == fname
    assert zf.filename_length == fname_len
    assert zf.comment_length == com_len
    assert zf.compressed_size == size
    assert zf.compressed_size == zf.uncompressed_size
    assert zf.file_range.start == rng_start
    assert zf.file_range.end == rng_end


@mark.parametrize("expected", ["ZippedFileInfo 'example_text_file.txt' @ 0: 11B"])
def test_zip_repr(example_zip_stream, expected):
    assert example_zip_stream.zipped_files[0].__repr__() == expected
