from ssl import SSLContext
from typing import Any, Dict, List, Optional, Union

from websockets.datastructures import HeadersLike

from .common.adapters.websockets import WebSocketsAdapter
from .websockets_protocol import WebsocketsProtocolTransportBase


class WebsocketsTransport(WebsocketsProtocolTransportBase):
    """:ref:`Async Transport <async_transports>` used to execute GraphQL queries on
    remote servers with websocket connection.

    This transport uses asyncio and the websockets library in order to send requests
    on a websocket connection.
    """

    def __init__(
        self,
        url: str,
        *,
        headers: Optional[HeadersLike] = None,
        ssl: Union[SSLContext, bool] = False,
        init_payload: Optional[Dict[str, Any]] = None,
        connect_timeout: Optional[Union[int, float]] = 10,
        close_timeout: Optional[Union[int, float]] = 10,
        ack_timeout: Optional[Union[int, float]] = 10,
        keep_alive_timeout: Optional[Union[int, float]] = None,
        ping_interval: Optional[Union[int, float]] = None,
        pong_timeout: Optional[Union[int, float]] = None,
        answer_pings: bool = True,
        connect_args: Optional[Dict[str, Any]] = None,
        subprotocols: Optional[List[str]] = None,
    ) -> None:
        """Initialize the transport with the given parameters.

        :param url: The GraphQL server URL. Example: 'wss://server.com:PORT/graphql'.
        :param headers: Dict of HTTP Headers.
        :param ssl: ssl_context of the connection. Use ssl=False to disable encryption
        :param init_payload: Dict of the payload sent in the connection_init message.
        :param connect_timeout: Timeout in seconds for the establishment
            of the websocket connection. If None is provided this will wait forever.
        :param close_timeout: Timeout in seconds for the close. If None is provided
            this will wait forever.
        :param ack_timeout: Timeout in seconds to wait for the connection_ack message
            from the server. If None is provided this will wait forever.
        :param keep_alive_timeout: Optional Timeout in seconds to receive
            a sign of liveness from the server.
        :param ping_interval: Delay in seconds between pings sent by the client to
            the backend for the graphql-ws protocol. None (by default) means that
            we don't send pings. Note: there are also pings sent by the underlying
            websockets protocol. See the
            :ref:`keepalive documentation <websockets_transport_keepalives>`
            for more information about this.
        :param pong_timeout: Delay in seconds to receive a pong from the backend
            after we sent a ping (only for the graphql-ws protocol).
            By default equal to half of the ping_interval.
        :param answer_pings: Whether the client answers the pings from the backend
            (for the graphql-ws protocol).
            By default: True
        :param connect_args: Other parameters forwarded to
            `websockets.connect <https://websockets.readthedocs.io/en/stable/reference/\
            client.html#opening-a-connection>`_
        :param subprotocols: list of subprotocols sent to the
            backend in the 'subprotocols' http header.
            By default: both apollo and graphql-ws subprotocols.
        """

        # Instanciate a WebSocketAdapter to indicate the use
        # of the websockets dependency for this transport
        self.adapter: WebSocketsAdapter = WebSocketsAdapter(
            url=url,
            headers=headers,
            ssl=ssl,
            connect_args=connect_args,
        )

        # Initialize the WebsocketsProtocolTransportBase parent class
        super().__init__(
            adapter=self.adapter,
            init_payload=init_payload,
            connect_timeout=connect_timeout,
            close_timeout=close_timeout,
            ack_timeout=ack_timeout,
            keep_alive_timeout=keep_alive_timeout,
            ping_interval=ping_interval,
            pong_timeout=pong_timeout,
            answer_pings=answer_pings,
            subprotocols=subprotocols,
        )

    @property
    def headers(self) -> Optional[HeadersLike]:
        return self.adapter.headers

    @property
    def ssl(self) -> Union[SSLContext, bool]:
        return self.adapter.ssl
