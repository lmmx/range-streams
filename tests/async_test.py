import asyncio
from functools import partial
from signal import SIGINT

from pytest import fixture, mark, raises
from ranges import Range

from range_streams import _EXAMPLE_PNG_URL, _EXAMPLE_ZIP_URL, RangeStream
from range_streams.async_utils import AsyncFetcher, SignalHaltError
from range_streams.codecs import PngStream

from .data import EXAMPLE_FILE_LENGTH, EXAMPLE_SMALL_PNG_URL, EXAMPLE_URL

# https://tonybaloney.github.io/posts/async-test-patterns-for-pytest-and-unittest.html

THREE_URLS = [EXAMPLE_URL, _EXAMPLE_PNG_URL, _EXAMPLE_ZIP_URL]

default_kwargs = dict(stream_cls=RangeStream, show_progress_bar=False)


class CallbackMutatedClass:
    values = []

    @classmethod
    def reset(cls):
        """
        Reset the class attribute where tests store the URLs they called back from
        """
        cls.values = []


async def url_callback_func(fetcher, range_stream, url):
    """
    Async function which puts the URL onto the storage class's list of values
    """
    return CallbackMutatedClass.values.append(url)


async def stream_callback_func(fetcher, range_stream, url):
    """
    Async function which puts the stream object onto the storage class's list of values
    """
    return CallbackMutatedClass.values.append(range_stream)


async def read_png_callback_func(fetcher, png_stream, url):
    """
    Async function which puts the stream object onto the storage class's list of values
    """
    await png_stream.enumerate_chunks_async()
    # await png_stream.scan_ihdr_async()
    return CallbackMutatedClass.values.append(png_stream)


async def sigint_callback_func(fetcher, range_stream, url):
    """
    Mimic the act of sending the signal interrupt by raising it in a callback
    """
    await url_callback_func(fetcher, range_stream, url)
    # raise KeyboardInterrupt ?
    loop = asyncio.get_running_loop()
    fetcher.immediate_exit(signal_enum=SIGINT, loop=loop)


@mark.parametrize("cb", [None, url_callback_func])
@mark.parametrize("verbose", [True, False])
@mark.parametrize("error_msg", ["The list of URLs to fetch cannot be empty"])
@mark.parametrize("urls", [([]), (THREE_URLS)])
def test_fetcher(urls, error_msg, verbose, cb):
    """
    Fetch lists of 0 or 3 URLs asynchronously, with/out a callback, verbosely/quietly.
    """
    kwargs = dict(**default_kwargs, callback=cb, urls=urls, verbose=verbose)
    if urls == []:
        with raises(ValueError, match=error_msg):
            fetched = AsyncFetcher(**kwargs)
    else:
        fetched = AsyncFetcher(**kwargs)
        fetched.make_calls()
        expected_values = set() if cb is None else set(urls)
        stored_urls = getattr(CallbackMutatedClass, "values")
        assert set(stored_urls) == set(expected_values)
        CallbackMutatedClass.reset()


@mark.parametrize("cb", [sigint_callback_func])
@mark.parametrize("error_msg", ["The list of URLs to fetch cannot be empty"])
@mark.parametrize("urls", [(THREE_URLS)])
def test_fetcher_sigint(urls, error_msg, cb):
    """
    Fetch lists of 3 URLs asynchronously, with/out a callback, verbosely/quietly.
    Cannot figure out how to emulate passing the SIGINT from this test so can't catch,
    best I can do here is to check that the loop is stopped at the first callback when
    ``immediate_exit`` is called.
    """
    kwargs = dict(**default_kwargs, callback=cb, urls=urls, verbose=False)
    fetched = AsyncFetcher(**kwargs)
    # with raises(SignalHaltError, match=error_msg):
    fetched.make_calls()
    stored_urls = getattr(CallbackMutatedClass, "values")
    assert len(stored_urls) == 1
    assert set(stored_urls) < set(urls)
    CallbackMutatedClass.reset()


@mark.parametrize("stream_cls", [RangeStream, PngStream])
@mark.parametrize("cb", [None, stream_callback_func])
@mark.parametrize("error_msg", ["The list of URLs to fetch cannot be empty"])
@mark.parametrize(
    "urls",
    [
        ([]),
        ([_EXAMPLE_PNG_URL, EXAMPLE_SMALL_PNG_URL]),
    ],
)
def test_fetcher_classmethod(urls, error_msg, cb, stream_cls):
    """
    Fetch lists of 0 or 2 URLs asynchronously, with/out a callback, using the
    classmethod constructor of the ``stream_cls`` (RangeStream or a subclass).
    """
    kwargs = dict(callback=cb, urls=urls, show_progress_bar=False, verbose=False)
    if urls == []:
        with raises(ValueError, match=error_msg):
            fetched = stream_cls.make_async_fetcher(**kwargs)
    else:
        fetched = stream_cls.make_async_fetcher(**kwargs)
        fetched.make_calls()
        expected_values = set() if cb is None else set([stream_cls])
        stored_classes = list(map(type, getattr(CallbackMutatedClass, "values")))
        assert set(stored_classes) == set(expected_values)
        CallbackMutatedClass.reset()


@mark.parametrize("cb", [read_png_callback_func])
@mark.parametrize("urls", [([_EXAMPLE_PNG_URL, EXAMPLE_SMALL_PNG_URL])])
def test_fetcher_classmethod_read_png(urls, cb):
    """
    Fetch list of 2 PNG URLs asynchronously, with a callback that reads them, using the
    ``make_async_fetcher`` classmethod constructor.
    """
    kwargs = dict(callback=cb, urls=urls, show_progress_bar=False, verbose=False)
    stream_cls = PngStream
    fetched = stream_cls.make_async_fetcher(**kwargs)
    fetched.make_calls()
    expected_values = set() if cb is None else set([stream_cls])
    stored_classes = list(map(type, getattr(CallbackMutatedClass, "values")))
    assert set(stored_classes) == set(expected_values)
    CallbackMutatedClass.reset()
