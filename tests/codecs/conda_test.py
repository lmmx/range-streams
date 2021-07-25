from __future__ import annotations

from pytest import mark  # , fixture, raises

from range_streams.codecs import CondaStream

from .data import EXAMPLE_CONDA_URL


@mark.parametrize("expected", [83498])
def test_conda_total_bytes(expected):
    stream = CondaStream(url=EXAMPLE_CONDA_URL)
    assert stream.total_bytes == expected


@mark.parametrize("entries,start_c,start_e", [(3, 224, 83476)])
def test_conda_cd_meta(entries, start_c, start_e):
    stream = CondaStream(url=EXAMPLE_CONDA_URL)
    stream.check_end_of_central_dir_rec()
    assert stream.data.CTRL_DIR_REC.entry_count == entries
    assert stream.data.CTRL_DIR_REC.start_pos == start_c
    assert stream.data.E_O_CTRL_DIR_REC.start_pos == start_e


@mark.parametrize("expected", [[b"pkg-tqdm-4.61.1-pyhd3eb1b0_1.tar.zst"]])
def test_conda_zip_files(expected):
    stream = CondaStream(url=EXAMPLE_CONDA_URL)
    assert stream.file_list == expected
