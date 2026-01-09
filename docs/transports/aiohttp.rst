.. _aiohttp_transport:

AIOHTTPTransport
================

This transport uses the `aiohttp`_ library and allows you to send GraphQL queries using the HTTP protocol.

Reference: :class:`gql.transport.aiohttp.AIOHTTPTransport`

This transport supports both standard GraphQL operations (queries, mutations) and subscriptions.
Subscriptions are implemented using the `multipart subscription protocol`_
as implemented by Apollo GraphOS Router and other compatible servers.

This provides an HTTP-based alternative to WebSocket transports for receiving streaming
subscription updates. It's particularly useful when:

- WebSocket connections are not available or blocked by infrastructure
- You want to use standard HTTP with existing load balancers and proxies
- The backend implements the multipart subscription protocol

Queries
-------

.. literalinclude:: ../code_examples/aiohttp_async.py

Subscriptions
-------------

The transport sends a standard HTTP POST request with an ``Accept`` header indicating
support for multipart responses:

.. code-block:: text

    Accept: multipart/mixed;subscriptionSpec="1.0", application/json

The server responds with a ``multipart/mixed`` content type and streams subscription
updates as separate parts in the response body. Each part contains a JSON payload
with GraphQL execution results.

.. literalinclude:: ../code_examples/aiohttp_multipart_subscription.py

How It Works
^^^^^^^^^^^^

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

Limitations
^^^^^^^^^^^

- Subscriptions require the server to implement the multipart subscription protocol
- Long-lived connections may be terminated by intermediate proxies or load balancers
- Some server configurations may not support HTTP/1.1 chunked transfer encoding required for streaming

Authentication
--------------

There are multiple ways to authenticate depending on the server configuration.

1. Using HTTP Headers

.. code-block:: python

    transport = AIOHTTPTransport(
        url='https://SERVER_URL:SERVER_PORT/graphql',
        headers={'Authorization': 'token'}
    )

2. Using HTTP Cookies

You can manually set the cookies which will be sent with each connection:

.. code-block:: python

    transport = AIOHTTPTransport(url=url, cookies={"cookie1": "val1"})

Or you can use a cookie jar to save cookies set from the backend and reuse them later.

In some cases, the server will set some connection cookies after a successful login mutation
and you can save these cookies in a cookie jar to reuse them in a following connection
(See `issue 197`_):

.. code-block:: python

    jar = aiohttp.CookieJar()
    transport = AIOHTTPTransport(url=url, client_session_args={'cookie_jar': jar})


.. _aiohttp: https://docs.aiohttp.org
.. _issue 197: https://github.com/graphql-python/gql/issues/197
.. _multipart subscription protocol: https://www.apollographql.com/docs/graphos/routing/operations/subscriptions/multipart-protocol

