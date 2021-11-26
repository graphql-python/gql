.. _aiohttp_transport:

AIOHTTPTransport
================

This transport uses the `aiohttp`_ library and allows you to send GraphQL queries using the HTTP protocol.

Reference: :class:`gql.transport.aiohttp.AIOHTTPTransport`

.. note::

    GraphQL subscriptions are not supported on the HTTP transport.
    For subscriptions you should use the :ref:`websockets transport <websockets_transport>`.

.. literalinclude:: ../code_examples/aiohttp_async.py

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
