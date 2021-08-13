from __future__ import annotations

import asyncio
import time
from asyncio.events import AbstractEventLoop
from functools import partial
from signal import SIGINT, SIGTERM, Signals
from sys import stderr
from typing import TYPE_CHECKING, Callable, Coroutine, Iterator, Type

from aiostream import stream
from ranges import Range, RangeSet

MYPY = False  # when using mypy will be overrided as True
if MYPY or not TYPE_CHECKING:  # pragma: no cover
    import httpx  # avoid importing to Sphinx type checker

import tqdm
from tqdm.asyncio import tqdm_asyncio

from .log_utils import log, set_up_logging
from .types import _T as RangeStreamOrSubclass

__all__ = ["SignalHaltError", "AsyncFetcher"]


class AsyncFetcher:
    def __init__(
        self,
        stream_cls: Type[RangeStreamOrSubclass],
        urls: list[str],
        callback: Callable | None = None,
        verbose: bool = False,
        show_progress_bar: bool = True,
        timeout_s: float = 5.0,
        client=None,
        **kwargs,
    ):
        """
        Any kwargs are passed through to the stream class constructor.

        Args:
          callback : A function to be passed 3 values: the AsyncFetcher which is calling
                     it, the awaited RangeStream, and its source URL (a ``httpx.URL``,
                     which can be coerced to a string).
        """
        if urls == []:
            raise ValueError("The list of URLs to fetch cannot be empty")
        self.stream_cls = stream_cls
        self.stream_cls_kwargs = kwargs
        self.url_list = urls
        self.callback = callback
        self.n = len(urls)
        self.verbose = verbose
        self.show_progress_bar = show_progress_bar and not self.verbose
        self.client = client
        self.timeout = httpx.Timeout(timeout=timeout_s)
        self.completed = RangeSet()
        set_up_logging(quiet=not verbose)

    def make_calls(self):
        """
        The method called to run the event loop to fetch URLs, after initialisation
        and/or repeatedly upon exitting the loop (i.e. it can recover from errors).
        """
        urlset = (u for u in self.filtered_url_list)  # single use URL generator
        if self.show_progress_bar:
            self.set_up_progress_bar()
        self.fetch_things(urls=urlset)
        if self.show_progress_bar:
            self.pbar.close()

    async def process_stream(self, range_stream: RangeStreamOrSubclass):
        """
        Process an awaited RangeStream within an async fetch loop, calling the callback
        set on the `~range_streams.async_utils.AsyncFetcher.callback` attribute.

        Args:
          range_stream : The awaited RangeStream (or one of its subclasses)
        """
        monostream_response = range_stream._ranges[range_stream.total_range]
        resp = monostream_response.request.response  # httpx.Response
        source_url = resp.history[0].url if resp.history else resp.url
        # Map the response back to the thing it came from in the url_list
        i = next(i for (i, u) in enumerate(self.url_list) if source_url == u)
        if self.callback is not None:
            await self.callback(self, range_stream, source_url)
        if self.verbose:
            log.debug(f"Processed URL in async callback: {source_url}")
        if self.show_progress_bar:
            self.pbar.update()
        self.complete_row(row_index=i)
        await resp.aclose()

    def mark_url_complete(self, url: str):
        """
        Add the row index for the given URL in the
        :attr:`~range_streams.async_utils.AsyncFetcher.url_list` to the
        :attr:`~range_streams.async_utils.AsyncFetcher.completed`
        :class:`~ranges.RangeSet`, meaning it will be omitted on any further call to
        :meth:`~range_streams.async_utils.AsyncFetcher.make_calls`. This should be done
        to indicate the URL has been processed (either successfully or unsuccessfully,
        e.g. it gave a 404).
        """
        url_row_index = self.url_list.index(url)
        self.complete_row(row_index=url_row_index)

    def complete_row(self, row_index: int):
        """
        Add the range corresponding to the range at row ``row_index`` to the
        :attr:`~range_streams.async_utils.AsyncFetcher.completed`
        :class:`~ranges.RangeSet`, meaning it will be omitted on any further call to
        :meth:`~range_streams.async_utils.AsyncFetcher.make_calls`. This should be done
        to indicate the URL at that row has been processed (either successfully or
        unsuccessfully, e.g. it gave a 404).
        """
        row_range = Range(row_index, row_index + 1)
        self.completed.add(row_range)

    @property
    def filtered_url_list(self) -> list[str]:
        if self.completed.isempty():
            urls = self.url_list
        else:
            urls = [u for (i, u) in enumerate(self.url_list) if i not in self.completed]
        return urls

    def set_up_progress_bar(self):
        n_already_fetched = self.n - len(self.filtered_url_list)
        self.pbar = tqdm_asyncio(total=self.n)
        if n_already_fetched:
            self.pbar.update(n_already_fetched)
            self.pbar.refresh()

    def fetch_things(self, urls: Iterator[str]):
        try:
            return asyncio.run(self.async_fetch_urlset(urls))
        except SignalHaltError as exc:
            if self.show_progress_bar:
                self.pbar.disable = True
                self.pbar.close()

    async def fetch(self, client, url) -> RangeStreamOrSubclass:
        """
        Args:
          client : ``httpx.AsyncClient``
          url    : ``httpx.URL``
        """
        s = self.stream_cls(
            url=str(url),
            client=client,
            single_request=True,
            force_async=True,
            **self.stream_cls_kwargs,
        )
        await s.add_async()
        return s

    async def async_fetch_urlset(
        self,
        urls: Iterator[str],
    ) -> Coroutine:
        """
        If the :attr:`~range_streams.async_utils.AsyncFetcher.client` is ``None``, create one
        in a contextmanager block (i.e. close it immediately after use), otherwise use
        the one provided, not in a contextmanager block (i.e. leave it up to the user to
        close the client).
        """
        await self.set_async_signal_handlers()
        if self.client is None:
            async with httpx.AsyncClient() as client:
                processed = await self.fetch_and_process(urls=urls, client=client)
        else:
            if self.client.is_closed:
                msg = (
                    "Cannot use a closed client to fetch.\n\nDid you attempt to retry "
                    " after using the client in a contextmanager block (which implicitly"
                    " closes after exiting the block) perhaps?"
                )
                raise ValueError(msg)
            # assert self.client is not None # give mypy a clue
            processed = await self.fetch_and_process(urls=urls, client=self.client)
        return processed

    async def fetch_and_process(self, urls: Iterator[str], client):
        assert isinstance(client, httpx.AsyncClient)  # Not type checked due to Sphinx
        client.timeout = self.timeout
        ws = stream.repeat(client)
        xs = stream.zip(ws, stream.iterate(urls))
        ys = stream.starmap(xs, self.fetch, ordered=False, task_limit=20)
        zs = stream.map(ys, self.process_stream)
        return await zs

    def immediate_exit(self, signal_enum: Signals, loop: AbstractEventLoop) -> None:
        loop.stop()
        halt_error = SignalHaltError(signal_enum=signal_enum)
        raise halt_error

    async def set_async_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()
        for signal_enum in [SIGINT, SIGTERM]:
            exit_func = partial(self.immediate_exit, signal_enum=signal_enum, loop=loop)
            loop.add_signal_handler(signal_enum, exit_func)


class SignalHaltError(SystemExit):
    def __init__(self, signal_enum: Signals):
        self.signal_enum = signal_enum
        print("", file=stderr)  # Newline after the signal sequence printed to console
        log.critical(msg=repr(self))
        super().__init__(self.exit_code)

    @property
    def exit_code(self) -> int:
        return self.signal_enum.value

    def __repr__(self) -> str:
        return f"Exitted due to {self.signal_enum.name}"


# def demo_fetch(url_list):
#    fetched = AsyncFetcher(urls=url_list, verbose=False)
#    try:
#        fetched.make_calls()
#    except Exception as exc:
#        log.debug("DEBUG ::" + repr(exc))  # Suppress it to log
#        print(f"... {exc!r}")
