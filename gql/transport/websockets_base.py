from ssl import SSLContext
from typing import Any, Dict, List, Optional, Union

from websockets.datastructures import HeadersLike
from websockets.typing import Subprotocol

from .common.adapters.websockets import WebSocketsAdapter
from .common.base import SubscriptionTransportBase


class WebsocketsTransportBase(SubscriptionTransportBase):
    """abstract :ref:`Async Transport <async_transports>` used to implement
    different websockets protocols.

    This transport uses asyncio and the websockets library in order to send requests
    on a websocket connection.
    """

    def __init__(
        self,
        url: str,
        *,
        headers: Optional[HeadersLike] = None,
        ssl: Union[SSLContext, bool] = False,
        init_payload: Dict[str, Any] = {},
        connect_timeout: Optional[Union[int, float]] = 10,
        close_timeout: Optional[Union[int, float]] = 10,
        ack_timeout: Optional[Union[int, float]] = 10,
        keep_alive_timeout: Optional[Union[int, float]] = None,
        connect_args: Dict[str, Any] = {},
        subprotocols: Optional[List[Subprotocol]] = None,
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
        :param connect_args: Other parameters forwarded to websockets.connect
        :param subprotocols: list of subprotocols sent to the
            backend in the 'subprotocols' http header.
        """

        if subprotocols is not None:
            connect_args.update({"subprotocols": subprotocols})

        # Instanciate a WebSocketAdapter to indicate the use
        # of the websockets dependency for this transport
        self.adapter: WebSocketsAdapter = WebSocketsAdapter(
            url,
            headers=headers,
            ssl=ssl,
            connect_args=connect_args,
        )

        # Initialize the generic SubscriptionTransportBase parent class
        super().__init__(
            adapter=self.adapter,
            connect_timeout=connect_timeout,
            close_timeout=close_timeout,
            keep_alive_timeout=keep_alive_timeout,
        )

        self.init_payload: Dict[str, Any] = init_payload
        self.ack_timeout: Optional[Union[int, float]] = ack_timeout

        self.payloads: Dict[str, Any] = {}
        """payloads is a dict which will contain the payloads received
        for example with the graphql-ws protocol: 'ping', 'pong', 'connection_ack'"""

    @property
    def url(self) -> str:
        return self.adapter.url

    @property
    def headers(self) -> Dict[str, str]:
        return self.adapter.headers

    @property
    def ssl(self) -> Union[SSLContext, bool]:
        return self.adapter.ssl

    @property
    def connect_args(self) -> Dict[str, Any]:
        return self.adapter.connect_args
