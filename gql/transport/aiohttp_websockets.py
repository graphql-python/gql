from ssl import SSLContext
from typing import Any, Dict, List, Literal, Mapping, Optional, Union

from aiohttp import BasicAuth, ClientSession, Fingerprint
from aiohttp.typedefs import LooseHeaders, StrOrURL

from .common.adapters.aiohttp import AIOHTTPWebSocketsAdapter
from .websockets_protocol import WebsocketsProtocolTransportBase


class AIOHTTPWebsocketsTransport(WebsocketsProtocolTransportBase):
    """:ref:`Async Transport <async_transports>` used to execute GraphQL queries on
    remote servers with websocket connection.

    This transport uses asyncio and the provided aiohttp adapter library
    in order to send requests on a websocket connection.
    """

    def __init__(
        self,
        url: StrOrURL,
        *,
        subprotocols: Optional[List[str]] = None,
        heartbeat: Optional[float] = None,
        auth: Optional[BasicAuth] = None,
        origin: Optional[str] = None,
        params: Optional[Mapping[str, str]] = None,
        headers: Optional[LooseHeaders] = None,
        proxy: Optional[StrOrURL] = None,
        proxy_auth: Optional[BasicAuth] = None,
        proxy_headers: Optional[LooseHeaders] = None,
        ssl: Optional[Union[SSLContext, Literal[False], Fingerprint]] = None,
        websocket_close_timeout: float = 10.0,
        receive_timeout: Optional[float] = None,
        ssl_close_timeout: Optional[Union[int, float]] = 10,
        connect_timeout: Optional[Union[int, float]] = 10,
        close_timeout: Optional[Union[int, float]] = 10,
        ack_timeout: Optional[Union[int, float]] = 10,
        keep_alive_timeout: Optional[Union[int, float]] = None,
        init_payload: Dict[str, Any] = {},
        ping_interval: Optional[Union[int, float]] = None,
        pong_timeout: Optional[Union[int, float]] = None,
        answer_pings: bool = True,
        session: Optional[ClientSession] = None,
        client_session_args: Optional[Dict[str, Any]] = None,
        connect_args: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize the transport with the given parameters.

        :param url: The GraphQL server URL. Example: 'wss://server.com:PORT/graphql'.
        :param subprotocols: list of subprotocols sent to the
            backend in the 'subprotocols' http header.
            By default: both apollo and graphql-ws subprotocols.
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
        :param headers: HTTP Headers that sent with every request
                        May be either *iterable of key-value pairs* or
                        :class:`~collections.abc.Mapping`
                        (e.g. :class:`dict`,
                        :class:`~multidict.CIMultiDict`).
        :param proxy: Proxy URL, :class:`str` or :class:`~yarl.URL` (optional)
        :param aiohttp.BasicAuth proxy_auth: an object that represents proxy HTTP
                                             Basic Authorization (optional)
        :param ssl: SSL validation mode. ``True`` for default SSL check
                      (:func:`ssl.create_default_context` is used),
                      ``False`` for skip SSL certificate validation,
                      :class:`aiohttp.Fingerprint` for fingerprint
                      validation, :class:`ssl.SSLContext` for custom SSL
                      certificate validation.
        :param float websocket_close_timeout: Timeout for websocket to close.
                                              ``10`` seconds by default
        :param float receive_timeout: Timeout for websocket to receive
                                      complete message.  ``None`` (unlimited)
                                      seconds by default
        :param ssl_close_timeout: Timeout in seconds to wait for the ssl connection
                                  to close properly
        :param connect_timeout: Timeout in seconds for the establishment
            of the websocket connection. If None is provided this will wait forever.
        :param close_timeout: Timeout in seconds for the close. If None is provided
            this will wait forever.
        :param ack_timeout: Timeout in seconds to wait for the connection_ack message
            from the server. If None is provided this will wait forever.
        :param keep_alive_timeout: Optional Timeout in seconds to receive
            a sign of liveness from the server.
        :param init_payload: Dict of the payload sent in the connection_init message.
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
        :param session: Optional aiohttp.ClientSession instance.
        :param client_session_args: Dict of extra args passed to
                `aiohttp.ClientSession`_
        :param connect_args: Dict of extra args passed to
                `aiohttp.ClientSession.ws_connect`_

        .. _aiohttp.ClientSession.ws_connect:
          https://docs.aiohttp.org/en/stable/client_reference.html#aiohttp.ClientSession.ws_connect
        .. _aiohttp.ClientSession:
          https://docs.aiohttp.org/en/stable/client_reference.html#aiohttp.ClientSession
        """

        # Instanciate a AIOHTTPWebSocketAdapter to indicate the use
        # of the aiohttp dependency for this transport
        self.adapter: AIOHTTPWebSocketsAdapter = AIOHTTPWebSocketsAdapter(
            url=url,
            headers=headers,
            ssl=ssl,
            session=session,
            client_session_args=client_session_args,
            connect_args=connect_args,
            heartbeat=heartbeat,
            auth=auth,
            origin=origin,
            params=params,
            proxy=proxy,
            proxy_auth=proxy_auth,
            proxy_headers=proxy_headers,
            websocket_close_timeout=websocket_close_timeout,
            receive_timeout=receive_timeout,
            ssl_close_timeout=ssl_close_timeout,
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
    def headers(self) -> Optional[LooseHeaders]:
        return self.adapter.headers

    @property
    def ssl(self) -> Optional[Union[SSLContext, Literal[False], Fingerprint]]:
        return self.adapter.ssl
