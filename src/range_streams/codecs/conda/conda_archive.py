from __future__ import annotations

from ranges import Range

from ..zip import ZipStream

__all__ = ["CondaStream"]


class CondaStream(ZipStream):
    def __init__(
        self,
        url: str,
        client=None,
        byte_range: Range | tuple[int, int] = Range("[0, 0)"),
        pruning_level: int = 0,
        scan_contents: bool = True,
    ):
        super().__init__(
            url=url,
            client=client,
            byte_range=byte_range,
            pruning_level=pruning_level,
            scan_contents=scan_contents,
        )
        if scan_contents:
            self.validate_files()

    def validate_files(self) -> None:
        """
        After :attr:`zipped_files` is set (as a list of
        :class:`~range_streams.codecs.zip.ZippedFileInfo`), validate
        that they meet the specification of the ``.conda`` file format.
        This means: 1 ``info-...tar.zst``, 1 ``pkg-...tar.zst``, and 1
        ``metadata.json``. The simplest way to uniquely identify them is to sort
        alphabetically by filename and check file prefixes/suffixes.
        """
        info_tzst, meta_json, pkg_tzst = sorted(
            self.zipped_files, key=lambda f: f.filename
        )
        prefixes = ["info-", "pkg-"]
        info_tzst_fn = info_tzst.filename
        pkg_tzst_fn = pkg_tzst.filename
        if not (
            (info_tzst_fn.startswith("info-") and info_tzst_fn.endswith(".tar.zst"))
            and (pkg_tzst_fn.startswith("pkg-") and pkg_tzst_fn.endswith(".tar.zst"))
        ):
            raise ValueError("Invalid .conda archive")
        self.info_tzst = info_tzst
        self.meta_json = meta_json
        self.pkg_tzst = pkg_tzst
        return
