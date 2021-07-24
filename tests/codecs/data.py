__all__ = [
    "EXAMPLE_ZIP_URL",
    "EXAMPLE_TAR_BZ2_URL",
    "EXAMPLE_TAR_GZIP_URL",
    "EXAMPLE_ZSTD_URL",
    "EXAMPLE_CONDA_URL",
]

EXAMPLE_ZIP_URL, EXAMPLE_TAR_BZ2_URL, EXAMPLE_TAR_GZIP_URL, EXAMPLE_ZSTD_URL = [
    (
        "https://github.com/lmmx/range-streams/raw/master/"
        f"data/example_text_file.txt.{ext}"
    )
    for ext in [
        "zip",
        "tar.bz2",
        "tar.gz",
        "zst",
    ]
]

EXAMPLE_CONDA_URL = (
    "https://github.com/lmmx/range-streams/raw/master/"
    "data/tqdm-4.61.1-pyhd3eb1b0_1.conda"
)
