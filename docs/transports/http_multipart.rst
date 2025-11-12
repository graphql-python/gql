.. _http_multipart_transport:

HTTPMultipartTransport
======================

This transport implements GraphQL subscriptions over HTTP using the `multipart subscription protocol`_
as implemented by Apollo GraphOS Router and other compatible servers.

This provides an HTTP-based alternative to WebSocket transports for receiving streaming
subscription updates. It's particularly useful when:

- WebSocket connections are not available or blocked by infrastructure
- You want to use standard HTTP with existing load balancers and proxies
- The backend implements the multipart subscription protocol

Reference: :class:`gql.transport.http_multipart_transport.HTTPMultipartTransport`

.. note::

    This transport is specifically designed for GraphQL subscriptions. While it can handle
    queries and mutations via the ``execute()`` method, standard HTTP transports like
    :ref:`AIOHTTPTransport <aiohttp_transport>` are more efficient for those operations.

.. literalinclude:: ../code_examples/http_multipart_async.py

How It Works
------------

The transport sends a standard HTTP POST request with an ``Accept`` header indicating
support for multipart responses:

.. code-block:: text

    Accept: multipart/mixed;subscriptionSpec="1.0", application/json

The server responds with a ``multipart/mixed`` content type and streams subscription
updates as separate parts in the response body. Each part contains a JSON payload
with GraphQL execution results.

Protocol Details
----------------

**Message Format**

Each message part follows this structure:

.. code-block:: text

    --graphql
    Content-Type: application/json

    {"payload": {"data": {...}, "errors": [...]}}

**Heartbeats**

Servers may send empty JSON objects (``{}``) as heartbeat messages to keep the
connection alive. These are automatically filtered out by the transport.

**Error Handling**

The protocol distinguishes between two types of errors:

- **GraphQL errors**: Returned within the ``payload`` property alongside data
- **Transport errors**: Returned with a top-level ``errors`` field and ``null`` payload

**End of Stream**

The subscription ends when the server sends the final boundary marker:

.. code-block:: text

    --graphql--

Authentication
--------------

Authentication works the same as with :ref:`AIOHTTPTransport <aiohttp_transport>`.

Using HTTP Headers
^^^^^^^^^^^^^^^^^^

.. code-block:: python

    transport = HTTPMultipartTransport(
        url='https://SERVER_URL:SERVER_PORT/graphql',
        headers={'Authorization': 'Bearer YOUR_TOKEN'}
    )

Using HTTP Cookies
^^^^^^^^^^^^^^^^^^

.. code-block:: python

    transport = HTTPMultipartTransport(
        url=url,
        cookies={"session_id": "your_session_cookie"}
    )

Or use a cookie jar to save and reuse cookies:

.. code-block:: python

    import aiohttp

    jar = aiohttp.CookieJar()
    transport = HTTPMultipartTransport(
        url=url,
        client_session_args={'cookie_jar': jar}
    )

Configuration
-------------

Timeout Settings
^^^^^^^^^^^^^^^^

Set a timeout for the HTTP request:

.. code-block:: python

    transport = HTTPMultipartTransport(
        url='https://SERVER_URL/graphql',
        timeout=30  # 30 second timeout
    )

SSL Configuration
^^^^^^^^^^^^^^^^^

Control SSL certificate verification:

.. code-block:: python

    transport = HTTPMultipartTransport(
        url='https://SERVER_URL/graphql',
        ssl=False  # Disable SSL verification (not recommended for production)
    )

Or provide a custom SSL context:

.. code-block:: python

    import ssl

    ssl_context = ssl.create_default_context()
    ssl_context.load_cert_chain('client.crt', 'client.key')

    transport = HTTPMultipartTransport(
        url='https://SERVER_URL/graphql',
        ssl=ssl_context
    )

Limitations
-----------

- This transport requires the server to implement the multipart subscription protocol
- Long-lived connections may be terminated by intermediate proxies or load balancers
- Some server configurations may not support HTTP/1.1 chunked transfer encoding required for streaming

.. _multipart subscription protocol: https://www.apollographql.com/docs/graphos/routing/operations/subscriptions/multipart-protocol
