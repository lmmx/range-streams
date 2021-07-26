__all__ = [
    "EXAMPLE_ZIP_URL",
    "EXAMPLE_TAR_BZ2_URL",
    "EXAMPLE_TAR_GZIP_URL",
    "EXAMPLE_ZSTD_URL",
    "EXAMPLE_CONDA_URL",
    "EXAMPLE_PNG_URL",
    "EXAMPLE_SEMITRANSPARENT_PNG_URL",
]

data_dir_URL = "https://github.com/lmmx/range-streams/raw/master/data/"

EXAMPLE_ZIP_URL, EXAMPLE_TAR_BZ2_URL, EXAMPLE_TAR_GZIP_URL, EXAMPLE_ZSTD_URL = [
    f"{data_dir_URL}example_text_file.txt.{ext}"
    for ext in "zip tar.bz2 tar.gz zst".split()
]

EXAMPLE_CONDA_URL = f"{data_dir_URL}tqdm-4.61.1-pyhd3eb1b0_1.conda"
EXAMPLE_PNG_URL = f"{data_dir_URL}red_square.png"
EXAMPLE_SEMITRANSPARENT_PNG_URL = f"{data_dir_URL}red_square_rgba_semitransparent.png"
