.. _websockets_transport:

WebsocketsTransport
===================

The websockets transport supports both:

 - the `Apollo websockets transport protocol`_.
 - the `GraphQL-ws websockets transport protocol`_

It will propose both subprotocols to the backend and detect the supported protocol
from the response http headers returned by the backend.

.. note::
    For some backends (graphql-ws before `version 5.6.1`_ without backwards compatibility), it may be necessary to specify
    only one subprotocol to the backend. It can be done by using
    :code:`subprotocols=[WebsocketsTransport.GRAPHQLWS_SUBPROTOCOL]`
    or :code:`subprotocols=[WebsocketsTransport.APOLLO_SUBPROTOCOL]` in the transport arguments.

This transport allows to do multiple queries, mutations and subscriptions on the same websocket connection.

Reference: :class:`gql.transport.websockets.WebsocketsTransport`

.. literalinclude:: ../code_examples/websockets_async.py

Websockets SSL
--------------

If you need to connect to an ssl encrypted endpoint:

* use :code:`wss` instead of :code:`ws` in the url of the transport

.. code-block:: python

    transport = WebsocketsTransport(
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

    transport = WebsocketsTransport(
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

    transport = WebsocketsTransport(
        url='wss://SERVER_URL:SERVER_PORT/graphql',
        headers={'Authorization': 'token'}
    )

2. With a payload in the connection_init websocket message

.. code-block:: python

    transport = WebsocketsTransport(
        url='wss://SERVER_URL:SERVER_PORT/graphql',
        init_payload={'Authorization': 'token'}
    )

.. _websockets_transport_keepalives:

Keep-Alives
-----------

Apollo protocol
^^^^^^^^^^^^^^^

With the Apollo protocol, the backend can optionally send unidirectional keep-alive ("ka") messages
(only from the server to the client).

It is possible to configure the transport to close if we don't receive a "ka" message
within a specified time using the :code:`keep_alive_timeout` parameter.

Here is an example with 60 seconds::

    transport = WebsocketsTransport(
        url='wss://SERVER_URL:SERVER_PORT/graphql',
        keep_alive_timeout=60,
    )

One disadvantage of the Apollo protocol is that because the keep-alives are only sent from the server
to the client, it can be difficult to detect the loss of a connection quickly from the server side.

GraphQL-ws protocol
^^^^^^^^^^^^^^^^^^^

With the GraphQL-ws protocol, it is possible to send bidirectional ping/pong messages.
Pings can be sent either from the client or the server and the other party should answer with a pong.

As with the Apollo protocol, it is possible to configure the transport to close if we don't
receive any message from the backend within the specified time using the :code:`keep_alive_timeout` parameter.

But there is also the possibility for the client to send pings at a regular interval and verify
that the backend sends a pong within a specified delay.
This can be done using the :code:`ping_interval` and :code:`pong_timeout` parameters.

Here is an example with a ping sent every 60 seconds, expecting a pong within 10 seconds::

    transport = WebsocketsTransport(
        url='wss://SERVER_URL:SERVER_PORT/graphql',
        ping_interval=60,
        pong_timeout=10,
    )

Underlying websockets protocol
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In addition to the keep-alives described above for the apollo and graphql-ws protocols,
there are also `ping frames`_ sent by the underlying websocket connection itself for both of them.

These pings are enabled by default (every 20 seconds) and could be modified or disabled
by passing extra arguments to the :code:`connect` call of the websockets client using the
:code:`connect_args` argument of the transport.

.. code-block:: python

    # Disabling websocket protocol level pings
    transport = WebsocketsTransport(
        url='wss://SERVER_URL:SERVER_PORT/graphql',
        connect_args={"ping_interval": None},
    )

See the `websockets keepalive documentation`_ for details.

.. _version 5.6.1: https://github.com/enisdenjo/graphql-ws/releases/tag/v5.6.1
.. _Apollo websockets transport protocol:  https://github.com/apollographql/subscriptions-transport-ws/blob/master/PROTOCOL.md
.. _GraphQL-ws websockets transport protocol: https://github.com/enisdenjo/graphql-ws/blob/master/PROTOCOL.md
.. _ping frames: https://www.rfc-editor.org/rfc/rfc6455.html#section-5.5.2
.. _websockets keepalive documentation: https://websockets.readthedocs.io/en/stable/topics/timeouts.html#keepalive-in-websockets
