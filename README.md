# range-requests

Testing the idea of streaming via range requests in Python

I came across
[`stream_response.py`](https://gist.github.com/obskyr/b9d4b4223e7eaf4eedcd9defabb34f13)
by GitHub user obskyr which encouraged me to pursue this idea I had
to stream GET requests for large files as file-like objects.

My idea is similar, except that rather than get the entire file,
what if you just wanted to download particular ranges, and
avoid downloading bytes for the parts you don't care about
(or defer downloading them until you do).

An example of a filetype which this would suit is `.zip`, which has well-defined
sections (see my [notes](https://github.com/lmmx/devnotes/wiki/Structure-of-zip-files)).

People want various things from zip files:

- the UK Department for International Trade [just want the files, and `pass` the central directory record entirely](https://github.com/uktrade/stream-unzip/blob/131767e806f09518cd51614ec7acd651099910bd/stream_unzip.py#L177-L181)),
- when surveying the Anaconda and Conda-Forge repositories of Python binaries,
  (using my tool [`impscan`](https://github.com/lmmx/impscan/)  parsing
  [`.conda` files](https://docs.conda.io/projects/conda/en/latest/user-guide/concepts/packages.html#conda-file-format)
  (which are zip files with a particular directory format), I want to _conditionally_ download the
  metadata and package binaries themselves (which are compressed in separate Zstd sub-archives of the
  `.conda` archive).
  - The package binary in particular will likely be rather larger, so I'd like to
    avoid needlessly downloading that if I don't need it (specifically if I don't need to check it for
    `site-packages` paths, if the metadata tells me it doesn't have any).

For this reason, sometimes you don't want the bytes from the server for a particular part of a file,
and if the headers returned by the server from a GET request include `Accept-Ranges': 'bytes'` then
that means it supports [HTTP range requests](https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests)

Here's an excerpt of the headers returned when I request
[a packaged `tqdm` build](https://repo.anaconda.com/pkgs/main/noarch/tqdm-4.61.1-pyhd3eb1b0_1.conda):

```py
 'Content-Length': '83498',
 'Content-Type': 'binary/octet-stream',
```

and here's what you get when adding a range header to just get 2 bytes
using `requests.get(url, headers={"range": "bytes=0-1"})`:

```py
 'Content-Length': '2',
 'Content-Range': 'bytes 0-1/83498',
 'Content-Type': 'binary/octet-stream'
```

When you send a HTTP range GET request rather than a regular one, note you get back
the additional "Content-Range" header. This can be used in an equivalent way to
`seek` on a file, and can avoid the routine you sometimes see (such as in the Python standard library's
`zipfile` module) of seeking to a negative index, then `tell()`ing the position of the
file cursor, to determine an absolute position from a relative position.

- For a zip file, you know the final 22 bytes contain the "end of central directory record",
  so this is my test case for this library as proof of concept.
