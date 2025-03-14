import logging
from ssl import SSLContext
from typing import Any, Dict, Optional, Union

import websockets
from websockets import ClientConnection
from websockets.datastructures import Headers, HeadersLike

from ...exceptions import TransportConnectionFailed, TransportProtocolError
from .connection import AdapterConnection

log = logging.getLogger("gql.transport.common.adapters.websockets")


class WebSocketsAdapter(AdapterConnection):
    """AdapterConnection implementation using the websockets library."""

    def __init__(
        self,
        url: str,
        *,
        headers: Optional[HeadersLike] = None,
        ssl: Union[SSLContext, bool] = False,
        connect_args: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize the transport with the given parameters.

        :param url: The GraphQL server URL. Example: 'wss://server.com:PORT/graphql'.
        :param headers: Dict of HTTP Headers.
        :param ssl: ssl_context of the connection. Use ssl=False to disable encryption
        :param connect_args: Other parameters forwarded to
            `websockets.connect <https://websockets.readthedocs.io/en/stable/reference/\
            client.html#opening-a-connection>`_
        """
        super().__init__(
            url=url,
            connect_args=connect_args,
        )

        self._headers: Optional[HeadersLike] = headers
        self.ssl = ssl

        self.websocket: Optional[ClientConnection] = None
        self._response_headers: Optional[Headers] = None

    async def connect(self) -> None:
        """Connect to the WebSocket server."""

        assert self.websocket is None

        ssl: Optional[Union[SSLContext, bool]]
        if self.ssl:
            ssl = self.ssl
        else:
            ssl = True if self.url.startswith("wss") else None

        # Set default arguments used in the websockets.connect call
        connect_args: Dict[str, Any] = {
            "ssl": ssl,
            "additional_headers": self.headers,
        }

        if self.subprotocols:
            connect_args["subprotocols"] = self.subprotocols

        # Adding custom parameters passed from init
        connect_args.update(self.connect_args)

        # Connection to the specified url
        try:
            self.websocket = await websockets.connect(self.url, **connect_args)
        except Exception as e:
            raise TransportConnectionFailed("Connect failed") from e

        assert self.websocket.response is not None

        self._response_headers = self.websocket.response.headers

    async def send(self, message: str) -> None:
        """Send message to the WebSocket server.

        Args:
            message: String message to send

        Raises:
            TransportConnectionFailed: If connection closed
        """
        if self.websocket is None:
            raise TransportConnectionFailed("WebSocket connection is already closed")

        try:
            await self.websocket.send(message)
        except Exception as e:
            raise TransportConnectionFailed(
                f"Error trying to send data: {type(e).__name__}"
            ) from e

    async def receive(self) -> str:
        """Receive message from the WebSocket server.

        Returns:
            String message received

        Raises:
            TransportConnectionFailed: If connection closed
            TransportProtocolError: If protocol error or binary data received
        """
        # It is possible that the websocket has been already closed in another task
        if self.websocket is None:
            raise TransportConnectionFailed("Connection is already closed")

        # Wait for the next websocket frame. Can raise ConnectionClosed
        try:
            data = await self.websocket.recv()
        except Exception as e:
            raise TransportConnectionFailed(
                f"Error trying to receive data: {type(e).__name__}"
            ) from e

        # websocket.recv() can return either str or bytes
        # In our case, we should receive only str here
        if not isinstance(data, str):
            raise TransportProtocolError("Binary data received in the websocket")

        answer: str = data

        return answer

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self.websocket:
            websocket = self.websocket
            self.websocket = None
            await websocket.close()

    @property
    def headers(self) -> Optional[HeadersLike]:
        """Get the response headers from the WebSocket connection.

        Returns:
            Dictionary of response headers
        """
        if self._headers:
            return self._headers
        return {}

    @property
    def response_headers(self) -> Dict[str, str]:
        """Get the response headers from the WebSocket connection.

        Returns:
            Dictionary of response headers
        """
        if self._response_headers:
            return dict(self._response_headers.raw_items())
        return {}
