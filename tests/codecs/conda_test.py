from __future__ import annotations

from pytest import fixture, mark, raises
from ranges import Range

from range_streams.codecs import CondaStream

from .data import EXAMPLE_CONDA_URL


@fixture
def example_conda_stream():
    return CondaStream(url=EXAMPLE_CONDA_URL)


@mark.parametrize("expected", [83498])
def test_conda_total_bytes(example_conda_stream, expected):
    assert example_conda_stream.total_bytes == expected


@mark.parametrize("entries,size,start_c,start_e", [(3, 224, 83252, 83476)])
def test_conda_cd_meta(example_conda_stream, entries, size, start_c, start_e):
    example_conda_stream.check_end_of_central_dir_rec()
    assert example_conda_stream.data.CTRL_DIR_REC.entry_count == entries
    assert example_conda_stream.data.CTRL_DIR_REC.size == size
    assert example_conda_stream.data.CTRL_DIR_REC.start_pos == start_c
    example_conda_stream.add(Range(start_c, start_c + 4))
    b = example_conda_stream.active_range_response.read()
    assert b == example_conda_stream.data.CTRL_DIR_REC.start_sig
    assert example_conda_stream.data.E_O_CTRL_DIR_REC.start_pos == start_e
    assert start_c + size == start_e


@mark.parametrize(
    "expected",
    [
        [
            "metadata.json",
            "info-tqdm-4.61.1-pyhd3eb1b0_1.tar.zst",
            "pkg-tqdm-4.61.1-pyhd3eb1b0_1.tar.zst",
        ]
    ],
)
def test_conda_zip_files(example_conda_stream, expected):
    assert example_conda_stream.filename_list == expected


@mark.parametrize(
    "fname1,fname_len1,com_len1,size1,rng_start1,rng_end1",
    [("metadata.json", 13, 0, 0, 43, 43)],
)
@mark.parametrize(
    "fname2,fname_len2,com_len2,size2,rng_start2,rng_end2",
    [("info-tqdm-4.61.1-pyhd3eb1b0_1.tar.zst", 37, 0, 29749, 110, 29859)],
)
@mark.parametrize(
    "fname3,fname_len3,com_len3,size3,rng_start3,rng_end3",
    [("pkg-tqdm-4.61.1-pyhd3eb1b0_1.tar.zst", 36, 0, 53327, 29925, 83252)],
)
def test_zipped_file_contents(
    example_conda_stream,
    fname1,
    fname_len1,
    com_len1,
    size1,
    rng_start1,
    rng_end1,
    fname2,
    fname_len2,
    com_len2,
    size2,
    rng_start2,
    rng_end2,
    fname3,
    fname_len3,
    com_len3,
    size3,
    rng_start3,
    rng_end3,
):
    zf_l = example_conda_stream.zipped_files
    assert len(zf_l) == 3
    zf1, zf2, zf3 = zf_l

    assert zf1.filename == fname1
    assert zf1.filename_length == fname_len1
    assert zf1.comment_length == com_len1
    assert zf1.compressed_size == size1
    assert zf1.compressed_size == zf1.uncompressed_size
    assert zf1.file_range.start == rng_start1
    assert zf1.file_range.end == rng_end1

    assert zf2.filename == fname2
    assert zf2.filename_length == fname_len2
    assert zf2.comment_length == com_len2
    assert zf2.compressed_size == size2
    assert zf2.compressed_size == zf2.uncompressed_size
    assert zf2.file_range.start == rng_start2
    assert zf2.file_range.end == rng_end2

    assert zf3.filename == fname3
    assert zf3.filename_length == fname_len3
    assert zf3.comment_length == com_len3
    assert zf3.compressed_size == size3
    assert zf3.compressed_size == zf3.uncompressed_size
    assert zf3.file_range.start == rng_start3
    assert zf3.file_range.end == rng_end3
