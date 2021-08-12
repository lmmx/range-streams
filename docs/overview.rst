Outline of ``RangeStream`` data structure
-----------------------------------------

A ``RangeStream`` is initialised by providing:

-  a URL (the file to be streamed)
-  a client (e.g. ``httpx.Client``)
-  (optionally) a range, as either:

   -  ``ranges.Range`` from the ``python-ranges`` package [recommended]
   -  or a tuple of integers, presumed to be a half-open interval
      inclusive of start/exclusive of stop as is common practice in
      Python — ``[start, stop)`` in `interval
      notation <https://en.wikipedia.org/wiki/Interval_(mathematics)#Notations_for_intervals>`__

Since every range request returns the total content length, the
``RangeStream`` will become capable of seeking to negative-valued ranges
(whose positions are in respect to the end) after fulfilling its first
range request.

If no range is provided upon initialisation then the range defaults to
``[0,0)``, the empty range, and a request will be sent to the server for
this (valid) range, whose only result will be to set the total file
length on the ``_length`` attribute of ``RangeStream`` (accessed through
the ``total_bytes`` property).

Once a request is made for a non-empty range, the ``RangeStream``
acquires the first entry in the ``RangeDict`` stored on the ``._ranges``
attribute. When using the ranges, you should access the ``ranges``
property (instead of the internal ``_ranges`` attribute), which takes
into account whether the bytes in each range’s ``RangeResponse`` are
exhausted or removed due to overlap with another range. See the design
docs for further details.

Example
=======

-  Adapted from ``tests/range_stream_core_test.py``
   (`source <https://github.com/lmmx/range-streams/blob/master/tests/range_stream_core_test.py>`__)

.. code:: py

   from range_streams import RangeStream, _EXAMPLE_URL

   stream = RangeStream(url=_EXAMPLE_URL)
   stream.add(byte_range=(0,3)) # or pass ranges.Range(0,3)

   stream.ranges

⇣

.. code:: py

   RangeDict{
     RangeSet{Range[0, 3)}: RangeResponse ⠶ [0, 3) @ 'example_text_file.txt' from raw.githubusercontent.com
   }

Further ranges are requested by simply calling ``RangeStream.add`` with
another Range object. You can also provide a byte range to the ``add``
method as a tuple of two integers, which will be interpreted per the
usual convention for ranges in Python, as a ``[a,b)`` half-open
interval.

.. code:: py

   stream.add(byte_range=(7,9))
   stream.ranges

⇣

.. code:: py

   RangeDict{
     RangeSet{Range[0, 3)}: RangeResponse ⠶ [0, 3) @ 'example_text_file.txt' from raw.githubusercontent.com,
     RangeSet{Range[7, 9)}: RangeResponse ⠶ [7, 9) @ 'example_text_file.txt' from raw.githubusercontent.com
   }
