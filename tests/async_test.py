import asyncio
from signal import SIGINT

from pytest import fixture, mark, raises
from ranges import Range

from range_streams import _EXAMPLE_PNG_URL, _EXAMPLE_ZIP_URL, RangeStream
from range_streams.async_utils import AsyncFetcher, SignalHaltError

from .data import EXAMPLE_FILE_LENGTH, EXAMPLE_URL

# https://tonybaloney.github.io/posts/async-test-patterns-for-pytest-and-unittest.html

THREE_URLS = [EXAMPLE_URL, _EXAMPLE_PNG_URL, _EXAMPLE_ZIP_URL]


class CallbackMutatedClass:
    values = []

    @classmethod
    def reset(cls):
        """
        Reset the class attribute where tests store the URLs they called back from
        """
        cls.values = []


async def demo_callback_func(fetcher, range_stream, url):
    return CallbackMutatedClass.values.append(url)


async def sigint_callback_func(fetcher, range_stream, url):
    """
    Mimic the act of sending the signal interrupt by raising it in a callback
    """
    await demo_callback_func(fetcher, range_stream, url)
    # raise KeyboardInterrupt ?
    loop = asyncio.get_running_loop()
    fetcher.immediate_exit(signal_enum=SIGINT, loop=loop)


@mark.parametrize("callback", [None, demo_callback_func])
@mark.parametrize("verbose", [True, False])
@mark.parametrize("error_msg", ["The list of URLs to fetch cannot be empty"])
@mark.parametrize("urls", [([]), (THREE_URLS)])
def test_fetcher(urls, error_msg, verbose, callback):
    """
    Fetch lists of 0 or 3 URLs asynchronously, with/out a callback, verbosely/quietly.
    """
    args = dict(callback=callback, urls=urls, verbose=verbose, show_progress_bar=False)
    if urls == []:
        with raises(ValueError, match=error_msg):
            fetched = AsyncFetcher(**args)
    else:
        fetched = AsyncFetcher(**args)
        fetched.make_calls()
        expected_values = set() if callback is None else set(urls)
        stored_urls = getattr(CallbackMutatedClass, "values")
        assert set(stored_urls) == set(expected_values)
        CallbackMutatedClass.reset()


@mark.parametrize("callback", [sigint_callback_func])
@mark.parametrize("error_msg", ["The list of URLs to fetch cannot be empty"])
@mark.parametrize("urls", [(THREE_URLS)])
def test_fetcher_sigint(urls, error_msg, callback):
    """
    Fetch lists of 3 URLs asynchronously, with/out a callback, verbosely/quietly.
    Cannot figure out how to emulate passing the SIGINT from this test so can't catch,
    best I can do here is to check that the loop is stopped at the first callback when
    ``immediate_exit`` is called.
    """
    args = dict(callback=callback, urls=urls, show_progress_bar=False)
    fetched = AsyncFetcher(**args)
    # with raises(SignalHaltError, match=error_msg):
    fetched.make_calls()
    stored_urls = getattr(CallbackMutatedClass, "values")
    assert len(stored_urls) == 1
    assert set(stored_urls) < set(urls)
    CallbackMutatedClass.reset()
