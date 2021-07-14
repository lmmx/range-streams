=============
API Reference
=============

.. automodule:: range_streams
   :members:

Range streams
=============

This class represents a file being streamed as a sequence of non-overlapping
ranges.

----

.. autoclass:: RangeStream

HTTP request helper functions
=============================

These helper functions help prepare HTTP requests to set up a stream.

----

.. autofunction:: range_streams.http_utils::byte_range_from_range_obj
.. autofunction:: range_streams.http_utils::range_header


Overlap handling
=================

These helper functions report on/handle the various possible ways ranges
can overlap, and the actions taken if an overlap is found.

----

.. autofunction:: range_streams.overlaps::get_range_containing
.. autofunction:: range_streams.overlaps::burn_range
.. autofunction:: range_streams.overlaps::handle_overlap
.. autofunction:: range_streams.overlaps::overlap_whence


Requests and responses
======================

These classes facilitate the streaming of data from a URL,
and handling the response as a file-like object.

----

.. autoclass:: range_streams.range_request::RangeRequest
.. autoclass:: range_streams.range_response::RangeResponse


Range operations
================

These tools perform transformations on, or output particular information from,
the data structures which store ranges.

----

.. autofunction:: range_streams.range_utils::ranges_in_reg_order
.. autofunction:: range_streams.range_utils::response_ranges_in_reg_order
.. autofunction:: range_streams.range_utils::most_recent_range
.. autofunction:: range_streams.range_utils::range_termini
.. autofunction:: range_streams.range_utils::range_len
.. autofunction:: range_streams.range_utils::range_min
.. autofunction:: range_streams.range_utils::range_max
.. autofunction:: range_streams.range_utils::validate_range
.. autofunction:: range_streams.range_utils::range_span
.. autofunction:: range_streams.range_utils::ext2int
