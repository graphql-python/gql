.. _aiohttp_websockets_transport:

AIOHTTPWebsocketsTransport
==========================

The AIOHTTPWebsocketsTransport is an alternative to the :ref:`websockets_transport`,
using the `aiohttp` dependency instead of the `websockets` dependency.

It also supports both:

 - the `Apollo websockets transport protocol`_.
 - the `GraphQL-ws websockets transport protocol`_

It will propose both subprotocols to the backend and detect the supported protocol
from the response http headers returned by the backend.

.. note::
    For some backends (graphql-ws before `version 5.6.1`_ without backwards compatibility), it may be necessary to specify
    only one subprotocol to the backend. It can be done by using
    :code:`subprotocols=[AIOHTTPWebsocketsTransport.GRAPHQLWS_SUBPROTOCOL]`
    or :code:`subprotocols=[AIOHTTPWebsocketsTransport.APOLLO_SUBPROTOCOL]` in the transport arguments.

This transport allows to do multiple queries, mutations and subscriptions on the same websocket connection.

Reference: :class:`gql.transport.aiohttp_websockets.AIOHTTPWebsocketsTransport`

.. literalinclude:: ../code_examples/aiohttp_websockets_async.py

.. _version 5.6.1: https://github.com/enisdenjo/graphql-ws/releases/tag/v5.6.1
.. _Apollo websockets transport protocol:  https://github.com/apollographql/subscriptions-transport-ws/blob/master/PROTOCOL.md
.. _GraphQL-ws websockets transport protocol: https://github.com/enisdenjo/graphql-ws/blob/master/PROTOCOL.md
