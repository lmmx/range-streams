from __future__ import annotations

from pytest import fixture, mark, raises
from ranges import Range

from range_streams.codecs import TarStream

from .data import EXAMPLE_TAR_URL


@fixture(scope="session")
def example_tar_stream():
    return TarStream(url=EXAMPLE_TAR_URL)


@mark.parametrize("expected", [8192])
def test_tar_total_bytes(example_tar_stream, expected):
    assert example_tar_stream.total_bytes == expected


@mark.parametrize(
    "expected", [(["red_square_rgba_semitransparent.png", "example_text_file.txt"])]
)
def test_tar_list_files(example_tar_stream, expected):
    assert example_tar_stream.filename_list == expected


@mark.parametrize(
    "file_i,size,padded_size,fname,fname_len,header_offset",
    [
        (0, 5124, 6144, "red_square_rgba_semitransparent.png", 35, 0),
        (1, 11, 1024, "example_text_file.txt", 21, 6144),
    ],
)
def test_tarred_file_contents(
    example_tar_stream, file_i, size, padded_size, fname, fname_len, header_offset
):
    tf_l = example_tar_stream.tarred_files
    assert len(tf_l) == 2
    tf = tf_l[file_i]
    assert tf.size == size
    assert tf.padded_size == padded_size
    assert tf.filename == fname
    assert tf.filename_length == fname_len
    assert tf.header_offset == header_offset


@mark.parametrize(
    "file_i,expected",
    [
        (0, "TarredFileInfo 'red_square_rgba_semitransparent.png' @ 0: 5124B"),
        (1, "TarredFileInfo 'example_text_file.txt' @ 6144: 11B"),
    ],
)
def test_tar_repr(example_tar_stream, file_i, expected):
    assert example_tar_stream.tarred_files[file_i].__repr__() == expected
