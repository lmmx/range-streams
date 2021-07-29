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
        """
        Set up a stream for the conda (ZIP) archive at ``url``, with either an initial
        range to be requested (HTTP partial content request), or if left
        as the empty range (default: ``Range(0,0)``) a HEAD request will
        be sent instead, so as to set the total size of the target
        file on the :attr:`~range_streams.stream.RangeStream.total_bytes`
        property.

        By default (if ``client`` is left as ``None``) a fresh
        :class:`httpx.Client` will be created for each stream.

        The ``byte_range`` can be specified as either a :class:`~ranges.Range`
        object, or 2-tuple of integers (``(start, end)``), interpreted
        either way as a half-closed interval ``[start, end)``, as given by
        Python's built-in :class:`range`.

        The ``pruning_level`` controls the policy for overlap handling
        (``0`` will resize overlapped ranges, ``1`` will delete overlapped
        ranges, and ``2`` will raise an error when a new range is added
        which overlaps a pre-existing range).

        - See docs for the
          :meth:`~range_streams.stream.RangeStream.handle_overlap`
          method for further details.

        Args:
          url           : (:class:`str`) The URL of the file to be streamed
          client        : (:class:`httpx.Client` | ``None``) The HTTPX client
                          to use for HTTP requests
          byte_range    : (:class:`~ranges.Range` | ``tuple[int,int]``) The range
                          of positions on the file to be requested
          pruning_level : (:class:`int`) Either ``0`` ('replant'), ``1`` ('burn'),
                          or ``2`` ('strict')
          scan_contents : (:class:`bool`) Whether to scan the archive contents
                          upon initialisation and add the archive's file ranges
        """
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
