from __future__ import annotations

from pytest import mark  # , fixture, raises

from range_streams.codecs import CondaStream

from .data import EXAMPLE_CONDA_URL


@mark.parametrize("expected", [83498])
def test_conda(expected):
    stream = CondaStream(url=EXAMPLE_CONDA_URL)
    assert stream.total_bytes == expected
