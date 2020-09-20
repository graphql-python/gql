.. _websockets_transport:

WebsocketsTransport
===================

The websockets transport implements the `Apollo websockets transport protocol`_.

This transport allows to do multiple queries, mutations and subscriptions on the same websocket connection.

.. literalinclude:: ../code_examples/websockets_async.py

Websockets SSL
--------------

If you need to connect to an ssl encrypted endpoint:

* use _wss_ instead of _ws_ in the url of the transport

.. code-block:: python

    sample_transport = WebsocketsTransport(
        url='wss://SERVER_URL:SERVER_PORT/graphql',
        headers={'Authorization': 'token'}
    )

If you have a self-signed ssl certificate, you need to provide an ssl_context with the server public certificate:

.. code-block:: python

    import pathlib
    import ssl

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    localhost_pem = pathlib.Path(__file__).with_name("YOUR_SERVER_PUBLIC_CERTIFICATE.pem")
    ssl_context.load_verify_locations(localhost_pem)

    sample_transport = WebsocketsTransport(
        url='wss://SERVER_URL:SERVER_PORT/graphql',
        ssl=ssl_context
    )

If you have also need to have a client ssl certificate, add:

.. code-block:: python

    ssl_context.load_cert_chain(certfile='YOUR_CLIENT_CERTIFICATE.pem', keyfile='YOUR_CLIENT_CERTIFICATE_KEY.key')

Websockets authentication
-------------------------

There are two ways to send authentication tokens with websockets depending on the server configuration.

1. Using HTTP Headers

.. code-block:: python

    sample_transport = WebsocketsTransport(
        url='wss://SERVER_URL:SERVER_PORT/graphql',
        headers={'Authorization': 'token'}
    )

2. With a payload in the connection_init websocket message

.. code-block:: python

    sample_transport = WebsocketsTransport(
        url='wss://SERVER_URL:SERVER_PORT/graphql',
        init_payload={'Authorization': 'token'}
    )

.. _Apollo websockets transport protocol:  https://github.com/apollographql/subscriptions-transport-ws/blob/master/PROTOCOL.md
