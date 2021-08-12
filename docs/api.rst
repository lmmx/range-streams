=============
API Reference
=============

.. automodule:: range_streams
   :members:
   :undoc-members:
   :show-inheritance:

Range streams
=============

This class represents a file being streamed as a sequence of non-overlapping
ranges.

----


.. automodule:: range_streams.stream
   :members:
   :undoc-members:
   :private-members: _ranges, _active_range
   :special-members: __init__, __ranges_repr__
   :show-inheritance:


HTTP request helper functions
=============================

These helper functions help prepare HTTP requests to set up a stream.

----


.. automodule:: range_streams.http_utils
   :members:
   :undoc-members:
   :show-inheritance:


Asynchronous fetcher
====================

This helper class handles all of the details of asynchronously
fetching streams, given a list of URLs.

----


.. automodule:: range_streams.async_utils
   :members:
   :undoc-members:
   :show-inheritance:


Overlap handling
=================

These helper functions report on/handle the various possible ways ranges
can overlap, and the actions taken if an overlap is found.

----


.. automodule:: range_streams.overlaps
   :members:
   :undoc-members:
   :show-inheritance:


Requests and responses
======================

These classes facilitate the streaming of data from a URL,
and handling the response as a file-like object.

----


.. automodule:: range_streams.request
   :members:
   :undoc-members:
   :show-inheritance:


.. automodule:: range_streams.response
   :members:
   :undoc-members:
   :show-inheritance:


Range operations
================

These tools perform transformations on, or output particular information from,
the data structures which store ranges.

----


.. automodule:: range_streams.range_utils
   :members:
   :undoc-members:
   :show-inheritance:

Streaming codecs
================

Codecs for PNG, ZIP, and .conda, and TAR formats to assist in handling these file types
in regard to the information in header sections defined in their specifications.

----


.. automodule:: range_streams.codecs.zip
   :members:
   :undoc-members:
   :special-members: __init__
   :show-inheritance:



.. automodule:: range_streams.codecs.conda
   :members:
   :undoc-members:
   :special-members: __init__
   :show-inheritance:


.. automodule:: range_streams.codecs.tar
   :members:
   :undoc-members:
   :special-members: __init__
   :show-inheritance:


.. automodule:: range_streams.codecs.png
   :members:
   :undoc-members:
   :special-members: __init__
   :show-inheritance:
