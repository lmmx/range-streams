from __future__ import annotations

from io import SEEK_END, SEEK_SET, BytesIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    # absolute imports for Sphinx
    import range_streams  # for RangeStream, RangeRequest

from .range_utils import range_len

__all__ = ["RangeResponse"]


class RangeResponse:
    """
    Adapted from `obskyr's ResponseStream demo code
    <https://gist.github.com/obskyr/b9d4b4223e7eaf4eedcd9defabb34f13>`_,
    this class handles the streamed partial request as a file-like object.
    """

    tail_mark: int = 0
    """
    The amount by which to shorten the 'tail' (i.e. the upper end) of the
    range when deciding if it is 'consumed'. Incremented within the
    :meth:`~range_streams.range_stream.RangeStream.handle_overlap` method
    when the ``pruning_level`` is set to ``1`` (indicating a "replant" policy).

    Under a 'replant' policy, when a new range is to be added and would overlap
    at the tail of an existing range, the pre-existing range should be effectively
    truncated by 'marking their tails'
    (where `an existing range` is assumed here to only be considered a range
    if it is not 'consumed' yet).
    """

    def __init__(
        self,
        stream: range_streams.RangeStream,
        range_request: range_streams.RangeRequest,
        range_name: str = "",
    ):
        self.parent_stream = stream
        self.request = range_request
        self._bytes = BytesIO()
        self.range_name = range_name

    def __repr__(self):
        rng_name = self.range_name if self.range_name == "" else f' "{self.range_name}"'
        return (
            f"{self.__class__.__name__} ⠶{rng_name} {self.request.range} @ "
            f"'{self.parent_stream.name}' from {self.parent_stream.domain}"
        )

    @property
    def _iterator(self):
        return self.request._iterator

    @property
    def client(self):
        return self.request.client

    @property
    def url(self) -> str:
        """
        A wrapper to access the :attr:`~range_streams.range_stream.RangeStream.url`
        of the 'parent' :class:`~range_streams.range_stream.RangeStream`.
        """
        return self.parent_stream.url

    @property
    def name(self) -> str:
        """
        A wrapper to access the :attr:`~range_streams.range_stream.RangeStream.name`
        of the 'parent' :class:`~range_streams.range_stream.RangeStream`.
        """
        return self.parent_stream.name

    def _load_all(self):
        self._bytes.seek(0, SEEK_END)
        for chunk in self._iterator:
            self._bytes.write(chunk)

    def _load_until(self, goal_position):
        current_position = self._bytes.seek(0, SEEK_END)
        while current_position < goal_position:
            try:
                current_position += self._bytes.write(next(self._iterator))
            except StopIteration:
                break

    def tell(self):
        """
        File-like tell (position indicator) within the range request stream.
        """
        return self._bytes.tell()

    def read(self, size=None):
        """
        File-like reading within the range request stream.
        """
        left_off_at = self._bytes.tell()
        if size is None:
            self._load_all()
        else:
            goal_position = left_off_at + size
            self._load_until(goal_position)

        self._bytes.seek(left_off_at)
        return self._bytes.read(size)

    def seek(self, position, whence=SEEK_SET):
        """
        File-like seeking within the range request stream.
        """
        if whence == SEEK_END:
            self._load_all()
        self._bytes.seek(position, whence)

    def is_consumed(self) -> bool:
        """
        Whether the :meth:`~range_streams.range_response.RangeResponse.tell`
        position (indicating 'consumed' or 'read so far') along with the
        :attr:`~range_streams.range_response.RangeResponse.tail_mark` indicates
        whether the stream should be considered consumed.

        The :attr:`~range_streams.range_response.RangeResponse.tail_mark`
        is part of a mechanism to 'shorten' ranges when an overlap is detected,
        to preserve the one-to-one integrity of the :class:`~ranges.RangeDict`
        (see notes on the "replant" policy of
        :meth:`~range_streams.range_stream.RangeStream.handle_overlap`, set
        by the ``pruning_level`` passed into
        :class:`~range_streams.range_stream.RangeStream` on initialisation).

        Note that there is (absolutely!) nothing stopping a stream from being
        re-consumed, but this library works on the assumption that all streams
        will be handled in an efficient manner (with any data read out from them
        either used once only or else will be reused from the first output rather
        than re-accessed directly from the stream itself).

        To this end, :class:`~range_streams.range_stream.RangeStream` has measures
        in place to "decommission" ranges once they are consumed (see in particular
        :meth:`~range_streams.range_stream.RangeStream.burn_range` and
        :meth:`~range_streams.range_stream.RangeStream.handle_overlap`).
        """
        read_so_far = self.tell()
        len_to_read = range_len(self.request.range) - self.tail_mark
        return read_so_far - len_to_read > 0
