import asyncio
import logging
from ssl import SSLContext
from typing import Any, Dict, Literal, Mapping, Optional, Union

import aiohttp
from aiohttp import BasicAuth, ClientWSTimeout, Fingerprint, WSMsgType
from aiohttp.typedefs import LooseHeaders, StrOrURL
from multidict import CIMultiDictProxy

from ...exceptions import TransportConnectionFailed, TransportProtocolError
from ..aiohttp_closed_event import create_aiohttp_closed_event
from .connection import AdapterConnection

log = logging.getLogger("gql.transport.common.adapters.aiohttp")


class AIOHTTPWebSocketsAdapter(AdapterConnection):
    """AdapterConnection implementation using the aiohttp library."""

    def __init__(
        self,
        url: StrOrURL,
        *,
        headers: Optional[LooseHeaders] = None,
        ssl: Optional[Union[SSLContext, Literal[False], Fingerprint]] = None,
        session: Optional[aiohttp.ClientSession] = None,
        client_session_args: Optional[Dict[str, Any]] = None,
        connect_args: Optional[Dict[str, Any]] = None,
        heartbeat: Optional[float] = None,
        auth: Optional[BasicAuth] = None,
        origin: Optional[str] = None,
        params: Optional[Mapping[str, str]] = None,
        proxy: Optional[StrOrURL] = None,
        proxy_auth: Optional[BasicAuth] = None,
        proxy_headers: Optional[LooseHeaders] = None,
        websocket_close_timeout: float = 10.0,
        receive_timeout: Optional[float] = None,
        ssl_close_timeout: Optional[Union[int, float]] = 10,
    ) -> None:
        """Initialize the transport with the given parameters.

        :param url: The GraphQL server URL. Example: 'wss://server.com:PORT/graphql'.
        :param headers: Dict of HTTP Headers.
        :param ssl: SSL validation mode. ``True`` for default SSL check
                      (:func:`ssl.create_default_context` is used),
                      ``False`` for skip SSL certificate validation,
                      :class:`aiohttp.Fingerprint` for fingerprint
                      validation, :class:`ssl.SSLContext` for custom SSL
                      certificate validation.
        :param session: Optional aiohttp opened session.
        :param client_session_args: Dict of extra args passed to
                :class:`aiohttp.ClientSession`
        :param connect_args: Dict of extra args passed to
                :meth:`aiohttp.ClientSession.ws_connect`

        :param float heartbeat: Send low level `ping` message every `heartbeat`
                                seconds and wait `pong` response, close
                                connection if `pong` response is not
                                received. The timer is reset on any data reception.
        :param auth: An object that represents HTTP Basic Authorization.
                     :class:`~aiohttp.BasicAuth` (optional)
        :param str origin: Origin header to send to server(optional)
        :param params: Mapping, iterable of tuple of *key*/*value* pairs or
                       string to be sent as parameters in the query
                       string of the new request. Ignored for subsequent
                       redirected requests (optional)

                       Allowed values are:

                       - :class:`collections.abc.Mapping` e.g. :class:`dict`,
                         :class:`multidict.MultiDict` or
                         :class:`multidict.MultiDictProxy`
                       - :class:`collections.abc.Iterable` e.g. :class:`tuple` or
                         :class:`list`
                       - :class:`str` with preferably url-encoded content
                         (**Warning:** content will not be encoded by *aiohttp*)
        :param proxy: Proxy URL, :class:`str` or :class:`~yarl.URL` (optional)
        :param aiohttp.BasicAuth proxy_auth: an object that represents proxy HTTP
                                             Basic Authorization (optional)
        :param float websocket_close_timeout: Timeout for websocket to close.
                                              ``10`` seconds by default
        :param float receive_timeout: Timeout for websocket to receive
                                      complete message.  ``None`` (unlimited)
                                      seconds by default
        :param ssl_close_timeout: Timeout in seconds to wait for the ssl connection
                                  to close properly
        """
        super().__init__(
            url=str(url),
            connect_args=connect_args,
        )

        self._headers: Optional[LooseHeaders] = headers
        self.ssl: Optional[Union[SSLContext, Literal[False], Fingerprint]] = ssl

        self.session: Optional[aiohttp.ClientSession] = session
        self._using_external_session = True if self.session else False

        if client_session_args is None:
            client_session_args = {}
        self.client_session_args = client_session_args

        self.heartbeat: Optional[float] = heartbeat
        self.auth: Optional[BasicAuth] = auth
        self.origin: Optional[str] = origin
        self.params: Optional[Mapping[str, str]] = params

        self.proxy: Optional[StrOrURL] = proxy
        self.proxy_auth: Optional[BasicAuth] = proxy_auth
        self.proxy_headers: Optional[LooseHeaders] = proxy_headers

        self.websocket_close_timeout: float = websocket_close_timeout
        self.receive_timeout: Optional[float] = receive_timeout

        self.ssl_close_timeout: Optional[Union[int, float]] = ssl_close_timeout

        self.websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self._response_headers: Optional[CIMultiDictProxy[str]] = None

    async def connect(self) -> None:
        """Connect to the WebSocket server."""

        assert self.websocket is None

        # Create a session if necessary
        if self.session is None:
            client_session_args: Dict[str, Any] = {}

            # Adding custom parameters passed from init
            client_session_args.update(self.client_session_args)  # type: ignore

            self.session = aiohttp.ClientSession(**client_session_args)

        ws_timeout = ClientWSTimeout(
            ws_receive=self.receive_timeout,
            ws_close=self.websocket_close_timeout,
        )

        connect_args: Dict[str, Any] = {
            "url": self.url,
            "headers": self.headers,
            "auth": self.auth,
            "heartbeat": self.heartbeat,
            "origin": self.origin,
            "params": self.params,
            "proxy": self.proxy,
            "proxy_auth": self.proxy_auth,
            "proxy_headers": self.proxy_headers,
            "timeout": ws_timeout,
        }

        if self.subprotocols:
            connect_args["protocols"] = self.subprotocols

        if self.ssl is not None:
            connect_args["ssl"] = self.ssl

        # Adding custom parameters passed from init
        connect_args.update(self.connect_args)

        try:
            self.websocket = await self.session.ws_connect(
                **connect_args,
            )
        except Exception as e:
            raise TransportConnectionFailed("Connect failed") from e

        self._response_headers = self.websocket._response.headers

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
            await self.websocket.send_str(message)
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

        while True:
            # Should not raise any exception:
            # https://docs.aiohttp.org/en/stable/_modules/aiohttp/client_ws.html
            #                                           #ClientWebSocketResponse.receive
            ws_message = await self.websocket.receive()

            # Ignore low-level ping and pong received
            if ws_message.type not in (WSMsgType.PING, WSMsgType.PONG):
                break

        if ws_message.type in (
            WSMsgType.CLOSE,
            WSMsgType.CLOSED,
            WSMsgType.CLOSING,
            WSMsgType.ERROR,
        ):
            raise TransportConnectionFailed("Connection was closed")
        elif ws_message.type is WSMsgType.BINARY:
            raise TransportProtocolError("Binary data received in the websocket")

        assert ws_message.type is WSMsgType.TEXT

        answer: str = ws_message.data

        return answer

    async def _close_session(self) -> None:
        """Close the aiohttp session."""

        assert self.session is not None

        closed_event = create_aiohttp_closed_event(self.session)
        await self.session.close()
        try:
            await asyncio.wait_for(closed_event.wait(), self.ssl_close_timeout)
        except asyncio.TimeoutError:
            pass
        finally:
            self.session = None

    async def close(self) -> None:
        """Close the WebSocket connection."""

        if self.websocket:
            websocket = self.websocket
            self.websocket = None
            try:
                await websocket.close()
            except Exception as exc:  # pragma: no cover
                log.warning("websocket.close() exception: " + repr(exc))

        if self.session and not self._using_external_session:
            await self._close_session()

    @property
    def headers(self) -> Optional[LooseHeaders]:
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
            return dict(self._response_headers)
        return {}
