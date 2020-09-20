AIOHTTPTransport
================

This transport uses the `aiohttp`_ library and allows you to send GraphQL queries using the HTTP protocol.

.. note::

    GraphQL subscriptions are not supported on the HTTP transport.
    For subscriptions you should use the :ref:`websockets transport <websockets_transport>`.

.. literalinclude:: ../code_examples/aiohttp_async.py

.. _aiohttp: https://docs.aiohttp.org
