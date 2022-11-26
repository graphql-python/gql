.. _httpx_async_transport:

HTTPXAsyncTransport
===================

This transport uses the `httpx`_ library and allows you to send GraphQL queries using the HTTP protocol.

Reference: :class:`gql.transport.httpx.HTTPXAsyncTransport`

.. note::

    GraphQL subscriptions are not supported on the HTTP transport.
    For subscriptions you should use the :ref:`websockets transport <websockets_transport>`.

.. literalinclude:: ../code_examples/httpx_async.py

Authentication
--------------

There are multiple ways to authenticate depending on the server configuration.

1. Using HTTP Headers

.. code-block:: python

    transport = HTTPXAsyncTransport(
        url='https://SERVER_URL:SERVER_PORT/graphql',
        headers={'Authorization': 'token'}
    )

2. Using HTTP Cookies

You can manually set the cookies which will be sent with each connection:

.. code-block:: python

    transport = HTTPXAsyncTransport(url=url, cookies={"cookie1": "val1"})

.. _httpx: https://www.python-httpx.org
