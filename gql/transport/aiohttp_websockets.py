import asyncio
import json
import logging
import warnings
from contextlib import suppress
from ssl import SSLContext
from typing import (
    Any,
    AsyncGenerator,
    Collection,
    Dict,
    Literal,
    Mapping,
    Optional,
    Tuple,
    Union,
)

import aiohttp
from aiohttp import BasicAuth, Fingerprint, WSMsgType
from aiohttp.typedefs import LooseHeaders, StrOrURL
from graphql import DocumentNode, ExecutionResult, print_ast
from multidict import CIMultiDictProxy

from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.async_transport import AsyncTransport
from gql.transport.exceptions import (
    TransportAlreadyConnected,
    TransportClosed,
    TransportProtocolError,
    TransportQueryError,
    TransportServerError,
)

log = logging.getLogger("gql.transport.aiohttp_websockets")

ParsedAnswer = Tuple[str, Optional[ExecutionResult]]


class ListenerQueue:
    """Special queue used for each query waiting for server answers

    If the server is stopped while the listener is still waiting,
    Then we send an exception to the queue and this exception will be raised
    to the consumer once all the previous messages have been consumed from the queue
    """

    def __init__(self, query_id: int, send_stop: bool) -> None:
        self.query_id: int = query_id
        self.send_stop: bool = send_stop
        self._queue: asyncio.Queue = asyncio.Queue()
        self._closed: bool = False

    async def get(self) -> ParsedAnswer:

        try:
            item = self._queue.get_nowait()
        except asyncio.QueueEmpty:
            item = await self._queue.get()

        self._queue.task_done()

        # If we receive an exception when reading the queue, we raise it
        if isinstance(item, Exception):
            self._closed = True
            raise item

        # Don't need to save new answers or
        # send the stop message if we already received the complete message
        answer_type, execution_result = item
        if answer_type == "complete":
            self.send_stop = False
            self._closed = True

        return item

    async def put(self, item: ParsedAnswer) -> None:

        if not self._closed:
            await self._queue.put(item)

    async def set_exception(self, exception: Exception) -> None:

        # Put the exception in the queue
        await self._queue.put(exception)

        # Don't need to send stop messages in case of error
        self.send_stop = False
        self._closed = True


class AIOHTTPWebsocketsTransport(AsyncTransport):

    # This transport supports two subprotocols and will autodetect the
    # subprotocol supported on the server
    APOLLO_SUBPROTOCOL: str = "graphql-ws"
    GRAPHQLWS_SUBPROTOCOL: str = "graphql-transport-ws"

    def __init__(
        self,
        url: StrOrURL,
        *,
        subprotocols: Optional[Collection[str]] = None,
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
        client_session_args: Optional[Dict[str, Any]] = None,
        connect_args: Dict[str, Any] = {},
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
        :param client_session_args: Dict of extra args passed to
                `aiohttp.ClientSession`_
        :param connect_args: Dict of extra args passed to
                `aiohttp.ClientSession.ws_connect`_

        .. _aiohttp.ClientSession.ws_connect:
          https://docs.aiohttp.org/en/stable/client_reference.html#aiohttp.ClientSession.ws_connect
        .. _aiohttp.ClientSession:
          https://docs.aiohttp.org/en/stable/client_reference.html#aiohttp.ClientSession
        """
        self.url: StrOrURL = url
        self.heartbeat: Optional[float] = heartbeat
        self.auth: Optional[BasicAuth] = auth
        self.origin: Optional[str] = origin
        self.params: Optional[Mapping[str, str]] = params
        self.headers: Optional[LooseHeaders] = headers

        self.proxy: Optional[StrOrURL] = proxy
        self.proxy_auth: Optional[BasicAuth] = proxy_auth
        self.proxy_headers: Optional[LooseHeaders] = proxy_headers

        self.ssl: Optional[Union[SSLContext, Literal[False], Fingerprint]] = ssl

        self.websocket_close_timeout: float = websocket_close_timeout
        self.receive_timeout: Optional[float] = receive_timeout

        self.ssl_close_timeout: Optional[Union[int, float]] = ssl_close_timeout
        self.connect_timeout: Optional[Union[int, float]] = connect_timeout
        self.close_timeout: Optional[Union[int, float]] = close_timeout
        self.ack_timeout: Optional[Union[int, float]] = ack_timeout
        self.keep_alive_timeout: Optional[Union[int, float]] = keep_alive_timeout

        self.init_payload: Dict[str, Any] = init_payload

        # We need to set an event loop here if there is none
        # Or else we will not be able to create an asyncio.Event()
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", message="There is no current event loop"
                )
                self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

        self._next_keep_alive_message: asyncio.Event = asyncio.Event()
        self._next_keep_alive_message.set()

        self.session: Optional[aiohttp.ClientSession] = None
        self.websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self.next_query_id: int = 1
        self.listeners: Dict[int, ListenerQueue] = {}
        self._connecting: bool = False
        self.response_headers: Optional[CIMultiDictProxy[str]] = None

        self.receive_data_task: Optional[asyncio.Future] = None
        self.check_keep_alive_task: Optional[asyncio.Future] = None
        self.close_task: Optional[asyncio.Future] = None

        self._wait_closed: asyncio.Event = asyncio.Event()
        self._wait_closed.set()

        self._no_more_listeners: asyncio.Event = asyncio.Event()
        self._no_more_listeners.set()

        self.payloads: Dict[str, Any] = {}

        self.ping_interval: Optional[Union[int, float]] = ping_interval
        self.pong_timeout: Optional[Union[int, float]]
        self.answer_pings: bool = answer_pings

        if ping_interval is not None:
            if pong_timeout is None:
                self.pong_timeout = ping_interval / 2
            else:
                self.pong_timeout = pong_timeout

        self.send_ping_task: Optional[asyncio.Future] = None

        self.ping_received: asyncio.Event = asyncio.Event()
        """ping_received is an asyncio Event which will fire  each time
        a ping is received with the graphql-ws protocol"""

        self.pong_received: asyncio.Event = asyncio.Event()
        """pong_received is an asyncio Event which will fire  each time
        a pong is received with the graphql-ws protocol"""

        self.supported_subprotocols: Collection[str] = subprotocols or (
            self.APOLLO_SUBPROTOCOL,
            self.GRAPHQLWS_SUBPROTOCOL,
        )

        self.close_exception: Optional[Exception] = None

        self.client_session_args = client_session_args
        self.connect_args = connect_args

    def _parse_answer_graphqlws(
        self, answer: Dict[str, Any]
    ) -> Tuple[str, Optional[int], Optional[ExecutionResult]]:
        """Parse the answer received from the server if the server supports the
        graphql-ws protocol.

        Returns a list consisting of:
            - the answer_type (between:
              'connection_ack', 'ping', 'pong', 'data', 'error', 'complete')
            - the answer id (Integer) if received or None
            - an execution Result if the answer_type is 'data' or None

        Differences with the apollo websockets protocol (superclass):
            - the "data" message is now called "next"
            - the "stop" message is now called "complete"
            - there is no connection_terminate or connection_error messages
            - instead of a unidirectional keep-alive (ka) message from server to client,
              there is now the possibility to send bidirectional ping/pong messages
            - connection_ack has an optional payload
            - the 'error' answer type returns a list of errors instead of a single error
        """

        answer_type: str = ""
        answer_id: Optional[int] = None
        execution_result: Optional[ExecutionResult] = None

        try:
            answer_type = str(answer.get("type"))

            if answer_type in ["next", "error", "complete"]:
                answer_id = int(str(answer.get("id")))

                if answer_type == "next" or answer_type == "error":

                    payload = answer.get("payload")

                    if answer_type == "next":

                        if not isinstance(payload, dict):
                            raise ValueError("payload is not a dict")

                        if "errors" not in payload and "data" not in payload:
                            raise ValueError(
                                "payload does not contain 'data' or 'errors' fields"
                            )

                        execution_result = ExecutionResult(
                            errors=payload.get("errors"),
                            data=payload.get("data"),
                            extensions=payload.get("extensions"),
                        )

                        # Saving answer_type as 'data' to be understood with superclass
                        answer_type = "data"

                    elif answer_type == "error":

                        if not isinstance(payload, list):
                            raise ValueError("payload is not a list")

                        raise TransportQueryError(
                            str(payload[0]), query_id=answer_id, errors=payload
                        )

            elif answer_type in ["ping", "pong", "connection_ack"]:
                self.payloads[answer_type] = answer.get("payload", None)

            else:
                raise ValueError

            if self.check_keep_alive_task is not None:
                self._next_keep_alive_message.set()

        except ValueError as e:
            raise TransportProtocolError(
                f"Server did not return a GraphQL result: {answer}"
            ) from e

        return answer_type, answer_id, execution_result

    def _parse_answer_apollo(
        self, answer: Dict[str, Any]
    ) -> Tuple[str, Optional[int], Optional[ExecutionResult]]:
        """Parse the answer received from the server if the server supports the
        apollo websockets protocol.

        Returns a list consisting of:
            - the answer_type (between:
              'connection_ack', 'ka', 'connection_error', 'data', 'error', 'complete')
            - the answer id (Integer) if received or None
            - an execution Result if the answer_type is 'data' or None
        """

        answer_type: str = ""
        answer_id: Optional[int] = None
        execution_result: Optional[ExecutionResult] = None

        try:
            answer_type = str(answer.get("type"))

            if answer_type in ["data", "error", "complete"]:
                answer_id = int(str(answer.get("id")))

                if answer_type == "data" or answer_type == "error":

                    payload = answer.get("payload")

                    if not isinstance(payload, dict):
                        raise ValueError("payload is not a dict")

                    if answer_type == "data":

                        if "errors" not in payload and "data" not in payload:
                            raise ValueError(
                                "payload does not contain 'data' or 'errors' fields"
                            )

                        execution_result = ExecutionResult(
                            errors=payload.get("errors"),
                            data=payload.get("data"),
                            extensions=payload.get("extensions"),
                        )

                    elif answer_type == "error":

                        raise TransportQueryError(
                            str(payload), query_id=answer_id, errors=[payload]
                        )

            elif answer_type == "ka":
                # Keep-alive message
                if self.check_keep_alive_task is not None:
                    self._next_keep_alive_message.set()
            elif answer_type == "connection_ack":
                pass
            elif answer_type == "connection_error":
                error_payload = answer.get("payload")
                raise TransportServerError(f"Server error: '{repr(error_payload)}'")
            else:
                raise ValueError

        except ValueError as e:
            raise TransportProtocolError(
                f"Server did not return a GraphQL result: {answer}"
            ) from e

        return answer_type, answer_id, execution_result

    def _parse_answer(
        self, answer: str
    ) -> Tuple[str, Optional[int], Optional[ExecutionResult]]:
        """Parse the answer received from the server depending on
        the detected subprotocol.
        """
        try:
            json_answer = json.loads(answer)
        except ValueError:
            raise TransportProtocolError(
                f"Server did not return a GraphQL result: {answer}"
            )

        if self.subprotocol == self.GRAPHQLWS_SUBPROTOCOL:
            return self._parse_answer_graphqlws(json_answer)

        return self._parse_answer_apollo(json_answer)

    async def _wait_ack(self) -> None:
        """Wait for the connection_ack message. Keep alive messages are ignored"""

        while True:
            init_answer = await self._receive()

            answer_type, _, _ = self._parse_answer(init_answer)

            if answer_type == "connection_ack":
                return

            if answer_type != "ka":
                raise TransportProtocolError(
                    "Websocket server did not return a connection ack"
                )

    async def _send_init_message_and_wait_ack(self) -> None:
        """Send init message to the provided websocket and wait for the connection ACK.

        If the answer is not a connection_ack message, we will return an Exception.
        """

        init_message = {"type": "connection_init", "payload": self.init_payload}

        await self._send(init_message)

        # Wait for the connection_ack message or raise a TimeoutError
        await asyncio.wait_for(self._wait_ack(), self.ack_timeout)

    async def _initialize(self):
        """Hook to send the initialization messages after the connection
        and potentially wait for the backend ack.
        """
        await self._send_init_message_and_wait_ack()

    async def _stop_listener(self, query_id: int):
        """Hook to stop to listen to a specific query.
        Will send a stop message in some subclasses.
        """
        log.debug(f"stop listener {query_id}")

        if self.subprotocol == self.GRAPHQLWS_SUBPROTOCOL:
            await self._send_complete_message(query_id)
            await self.listeners[query_id].put(("complete", None))
        else:
            await self._send_stop_message(query_id)

    async def _after_connect(self):
        """Hook to add custom code for subclasses after the connection
        has been established.
        """
        # Find the backend subprotocol returned in the response headers
        response_headers = self.websocket._response.headers
        log.debug(f"Response headers: {response_headers!r}")
        try:
            self.subprotocol = response_headers["Sec-WebSocket-Protocol"]
        except KeyError:
            self.subprotocol = self.APOLLO_SUBPROTOCOL

        log.debug(f"backend subprotocol returned: {self.subprotocol!r}")

    async def send_ping(self, payload: Optional[Any] = None) -> None:
        """Send a ping message for the graphql-ws protocol"""

        ping_message = {"type": "ping"}

        if payload is not None:
            ping_message["payload"] = payload

        await self._send(ping_message)

    async def send_pong(self, payload: Optional[Any] = None) -> None:
        """Send a pong message for the graphql-ws protocol"""

        pong_message = {"type": "pong"}

        if payload is not None:
            pong_message["payload"] = payload

        await self._send(pong_message)

    async def _send_stop_message(self, query_id: int) -> None:
        """Send stop message to the provided websocket connection and query_id.

        The server should afterwards return a 'complete' message.
        """

        stop_message = {"id": str(query_id), "type": "stop"}

        await self._send(stop_message)

    async def _send_complete_message(self, query_id: int) -> None:
        """Send a complete message for the provided query_id.

        This is only for the graphql-ws protocol.
        """

        complete_message = {"id": str(query_id), "type": "complete"}

        await self._send(complete_message)

    async def _send_ping_coro(self) -> None:
        """Coroutine to periodically send a ping from the client to the backend.

        Only used for the graphql-ws protocol.

        Send a ping every ping_interval seconds.
        Close the connection if a pong is not received within pong_timeout seconds.
        """

        assert self.ping_interval is not None

        try:
            while True:
                await asyncio.sleep(self.ping_interval)

                await self.send_ping()

                await asyncio.wait_for(self.pong_received.wait(), self.pong_timeout)

                # Reset for the next iteration
                self.pong_received.clear()

        except asyncio.TimeoutError:
            # No pong received in the appriopriate time, close with error
            # If the timeout happens during a close already in progress, do nothing
            if self.close_task is None:
                await self._fail(
                    TransportServerError(
                        f"No pong received after {self.pong_timeout!r} seconds"
                    ),
                    clean_close=False,
                )

    async def _after_initialize(self):
        """Hook to add custom code for subclasses after the initialization
        has been done.
        """

        # If requested, create a task to send periodic pings to the backend
        if (
            self.subprotocol == self.GRAPHQLWS_SUBPROTOCOL
            and self.ping_interval is not None
        ):

            self.send_ping_task = asyncio.ensure_future(self._send_ping_coro())

    async def _close_hook(self):
        """Hook to add custom code for subclasses for the connection close"""
        # Properly shut down the send ping task if enabled
        if self.send_ping_task is not None:
            self.send_ping_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.send_ping_task
            self.send_ping_task = None

    async def _connection_terminate(self):
        """Hook to add custom code for subclasses after the initialization
        has been done.
        """
        if self.subprotocol == self.APOLLO_SUBPROTOCOL:
            await self._send_connection_terminate_message()

    async def _send_connection_terminate_message(self) -> None:
        """Send a connection_terminate message to the provided websocket connection.

        This message indicates that the connection will disconnect.
        """

        connection_terminate_message = {"type": "connection_terminate"}

        await self._send(connection_terminate_message)

    async def _send_query(
        self,
        document: DocumentNode,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
    ) -> int:
        """Send a query to the provided websocket connection.

        We use an incremented id to reference the query.

        Returns the used id for this query.
        """

        query_id = self.next_query_id
        self.next_query_id += 1

        payload: Dict[str, Any] = {"query": print_ast(document)}
        if variable_values:
            payload["variables"] = variable_values
        if operation_name:
            payload["operationName"] = operation_name

        query_type = "start"

        if self.subprotocol == self.GRAPHQLWS_SUBPROTOCOL:
            query_type = "subscribe"

        query = {"id": str(query_id), "type": query_type, "payload": payload}

        await self._send(query)

        return query_id

    async def _send(self, message: Dict[str, Any]) -> None:
        """Send the provided message to the websocket connection and log the message"""

        if self.websocket is None:
            raise TransportClosed("WebSocket connection is closed")

        try:
            await self.websocket.send_json(message)
            log.info(">>> %s", message)
        except ConnectionResetError as e:
            await self._fail(e, clean_close=False)
            raise e

    async def _receive(self) -> str:
        """Wait the next message from the websocket connection and log the answer"""

        # It is possible that the websocket has been already closed in another task
        if self.websocket is None:
            raise TransportClosed("Transport is already closed")

        while True:
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
            raise ConnectionResetError
        elif ws_message.type is WSMsgType.BINARY:
            raise TransportProtocolError("Binary data received in the websocket")

        assert ws_message.type is WSMsgType.TEXT

        answer: str = ws_message.data

        log.info("<<< %s", answer)

        return answer

    def _remove_listener(self, query_id) -> None:
        """After exiting from a subscription, remove the listener and
        signal an event if this was the last listener for the client.
        """
        if query_id in self.listeners:
            del self.listeners[query_id]

        remaining = len(self.listeners)
        log.debug(f"listener {query_id} deleted, {remaining} remaining")

        if remaining == 0:
            self._no_more_listeners.set()

    async def _check_ws_liveness(self) -> None:
        """Coroutine which will periodically check the liveness of the connection
        through keep-alive messages
        """

        try:
            while True:
                await asyncio.wait_for(
                    self._next_keep_alive_message.wait(), self.keep_alive_timeout
                )

                # Reset for the next iteration
                self._next_keep_alive_message.clear()

        except asyncio.TimeoutError:
            # No keep-alive message in the appriopriate interval, close with error
            # while trying to notify the server of a proper close (in case
            # the keep-alive interval of the client or server was not aligned
            # the connection still remains)

            # If the timeout happens during a close already in progress, do nothing
            if self.close_task is None:
                await self._fail(
                    TransportServerError(
                        "No keep-alive message has been received within "
                        "the expected interval ('keep_alive_timeout' parameter)"
                    ),
                    clean_close=False,
                )

        except asyncio.CancelledError:
            # The client is probably closing, handle it properly
            pass

    async def _handle_answer(
        self,
        answer_type: str,
        answer_id: Optional[int],
        execution_result: Optional[ExecutionResult],
    ) -> None:

        try:
            # Put the answer in the queue
            if answer_id is not None:
                await self.listeners[answer_id].put((answer_type, execution_result))
        except KeyError:
            # Do nothing if no one is listening to this query_id.
            pass

        # Answer pong to ping for graphql-ws protocol
        if answer_type == "ping":
            self.ping_received.set()
            if self.answer_pings:
                await self.send_pong()

        elif answer_type == "pong":
            self.pong_received.set()

    async def _receive_data_loop(self) -> None:
        """Main asyncio task which will listen to the incoming messages and will
        call the parse_answer and handle_answer methods of the subclass."""
        log.debug("Entering _receive_data_loop()")

        try:
            while True:

                # Wait the next answer from the websocket server
                try:
                    answer = await self._receive()
                except (ConnectionResetError, TransportProtocolError) as e:
                    await self._fail(e, clean_close=False)
                    break
                except TransportClosed as e:
                    await self._fail(e, clean_close=False)
                    raise e

                # Parse the answer
                try:
                    answer_type, answer_id, execution_result = self._parse_answer(
                        answer
                    )
                except TransportQueryError as e:
                    # Received an exception for a specific query
                    # ==> Add an exception to this query queue
                    # The exception is raised for this specific query,
                    # but the transport is not closed.
                    assert isinstance(
                        e.query_id, int
                    ), "TransportQueryError should have a query_id defined here"
                    try:
                        await self.listeners[e.query_id].set_exception(e)
                    except KeyError:
                        # Do nothing if no one is listening to this query_id
                        pass

                    continue

                except (TransportServerError, TransportProtocolError) as e:
                    # Received a global exception for this transport
                    # ==> close the transport
                    # The exception will be raised for all current queries.
                    await self._fail(e, clean_close=False)
                    break

                await self._handle_answer(answer_type, answer_id, execution_result)

        finally:
            log.debug("Exiting _receive_data_loop()")

    async def connect(self) -> None:
        log.debug("connect: starting")

        if self.session is None:
            client_session_args: Dict[str, Any] = {}

            # Adding custom parameters passed from init
            if self.client_session_args:
                client_session_args.update(self.client_session_args)  # type: ignore

            self.session = aiohttp.ClientSession(**client_session_args)

        if self.websocket is None and not self._connecting:
            self._connecting = True

            connect_args: Dict[str, Any] = {
                "url": self.url,
                "headers": self.headers,
                "auth": self.auth,
                "heartbeat": self.heartbeat,
                "origin": self.origin,
                "params": self.params,
                "protocols": self.supported_subprotocols,
                "proxy": self.proxy,
                "proxy_auth": self.proxy_auth,
                "proxy_headers": self.proxy_headers,
                "timeout": self.websocket_close_timeout,
                "receive_timeout": self.receive_timeout,
            }

            if self.ssl is not None:
                connect_args.update(
                    {
                        "ssl": self.ssl,
                    }
                )

            # Adding custom parameters passed from init
            if self.connect_args:
                connect_args.update(self.connect_args)

            try:
                # Connection to the specified url
                # Generate a TimeoutError if taking more than connect_timeout seconds
                # Set the _connecting flag to False after in all cases
                self.websocket = await asyncio.wait_for(
                    self.session.ws_connect(
                        **connect_args,
                    ),
                    self.connect_timeout,
                )
            finally:
                self._connecting = False

            self.response_headers = self.websocket._response.headers

            await self._after_connect()

            self.next_query_id = 1
            self.close_exception = None
            self._wait_closed.clear()

            # Send the init message and wait for the ack from the server
            # Note: This should generate a TimeoutError
            # if no ACKs are received within the ack_timeout
            try:
                await self._initialize()
            except ConnectionResetError as e:
                raise e
            except (
                TransportProtocolError,
                TransportServerError,
                asyncio.TimeoutError,
            ) as e:
                await self._fail(e, clean_close=False)
                raise e

            # Run the after_init hook of the subclass
            await self._after_initialize()

            # If specified, create a task to check liveness of the connection
            # through keep-alive messages
            if self.keep_alive_timeout is not None:
                self.check_keep_alive_task = asyncio.ensure_future(
                    self._check_ws_liveness()
                )

            # Create a task to listen to the incoming websocket messages
            self.receive_data_task = asyncio.ensure_future(self._receive_data_loop())

        else:
            raise TransportAlreadyConnected("Transport is already connected")

        log.debug("connect: done")

    async def _clean_close(self) -> None:
        """Coroutine which will:

        - send stop messages for each active subscription to the server
        - send the connection terminate message
        """
        log.debug(f"Listeners: {self.listeners}")

        # Send 'stop' message for all current queries
        for query_id, listener in self.listeners.items():
            print(f"Listener {query_id} send_stop: {listener.send_stop}")

            if listener.send_stop:
                await self._stop_listener(query_id)
                listener.send_stop = False

        # Wait that there is no more listeners (we received 'complete' for all queries)
        try:
            await asyncio.wait_for(self._no_more_listeners.wait(), self.close_timeout)
        except asyncio.TimeoutError:  # pragma: no cover
            log.debug("Timer close_timeout fired")

        # Calling the subclass hook
        await self._connection_terminate()

    async def _close_coro(self, e: Exception, clean_close: bool = True) -> None:
        """Coroutine which will:

        - do a clean_close if possible:
            - send stop messages for each active query to the server
            - send the connection terminate message
        - close the websocket connection
        - send the exception to all the remaining listeners
        """

        log.debug("_close_coro: starting")

        try:

            try:
                # Properly shut down liveness checker if enabled
                if self.check_keep_alive_task is not None:
                    # More info: https://stackoverflow.com/a/43810272/1113207
                    self.check_keep_alive_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await self.check_keep_alive_task
            except Exception as exc:  # pragma: no cover
                log.warning(
                    "_close_coro cancel keep alive task exception: " + repr(exc)
                )

            try:
                # Calling the subclass close hook
                await self._close_hook()
            except Exception as exc:  # pragma: no cover
                log.warning("_close_coro close_hook exception: " + repr(exc))

            # Saving exception to raise it later if trying to use the transport
            # after it has already closed.
            self.close_exception = e

            if clean_close:
                log.debug("_close_coro: starting clean_close")
                try:
                    await self._clean_close()
                except Exception as exc:  # pragma: no cover
                    log.warning("Ignoring exception in _clean_close: " + repr(exc))

            log.debug("_close_coro: sending exception to listeners")

            # Send an exception to all remaining listeners
            for query_id, listener in self.listeners.items():
                await listener.set_exception(e)

            log.debug("_close_coro: close websocket connection")

            try:
                assert self.websocket is not None

                await self.websocket.close()
                self.websocket = None
            except Exception as exc:
                log.warning("_close_coro websocket close exception: " + repr(exc))

            log.debug("_close_coro: close aiohttp session")

            if (
                self.client_session_args
                and self.client_session_args.get("connector_owner") is False
            ):

                log.debug("connector_owner is False -> not closing connector")

            else:
                try:
                    assert self.session is not None

                    closed_event = AIOHTTPTransport.create_aiohttp_closed_event(
                        self.session
                    )
                    await self.session.close()
                    try:
                        await asyncio.wait_for(
                            closed_event.wait(), self.ssl_close_timeout
                        )
                    except asyncio.TimeoutError:
                        pass
                except Exception as exc:  # pragma: no cover
                    log.warning("_close_coro session close exception: " + repr(exc))

            self.session = None

            log.debug("_close_coro: aiohttp session closed")

            try:
                assert self.receive_data_task is not None

                self.receive_data_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self.receive_data_task
            except Exception as exc:  # pragma: no cover
                log.warning(
                    "_close_coro cancel receive data task exception: " + repr(exc)
                )

        except Exception as exc:  # pragma: no cover
            log.warning("Exception catched in _close_coro: " + repr(exc))

        finally:

            log.debug("_close_coro: final cleanup")

            self.websocket = None
            self.close_task = None
            self.check_keep_alive_task = None
            self.receive_data_task = None
            self._wait_closed.set()

        log.debug("_close_coro: exiting")

    async def _fail(self, e: Exception, clean_close: bool = True) -> None:
        log.debug("_fail: starting with exception: " + repr(e))

        if self.close_task is None:

            if self._wait_closed.is_set():
                log.debug("_fail started but transport is already closed")
            else:
                self.close_task = asyncio.shield(
                    asyncio.ensure_future(self._close_coro(e, clean_close=clean_close))
                )
        else:
            log.debug(
                "close_task is not None in _fail. Previous exception is: "
                + repr(self.close_exception)
                + " New exception is: "
                + repr(e)
            )

    async def close(self) -> None:
        log.debug("close: starting")

        await self._fail(TransportClosed("Websocket GraphQL transport closed by user"))
        await self.wait_closed()

        log.debug("close: done")

    async def wait_closed(self) -> None:
        log.debug("wait_close: starting")

        if not self._wait_closed.is_set():
            await self._wait_closed.wait()

        log.debug("wait_close: done")

    async def execute(
        self,
        document: DocumentNode,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute the provided document AST against the configured remote server
        using the current session.

        Send a query but close the async generator as soon as we have the first answer.

        The result is sent as an ExecutionResult object.
        """
        first_result = None

        generator = self.subscribe(
            document, variable_values, operation_name, send_stop=False
        )

        async for result in generator:
            first_result = result
            break

        if first_result is None:
            raise TransportQueryError(
                "Query completed without any answer received from the server"
            )

        return first_result

    async def subscribe(
        self,
        document: DocumentNode,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        send_stop: Optional[bool] = True,
    ) -> AsyncGenerator[ExecutionResult, None]:
        """Send a query and receive the results using a python async generator.

        The query can be a graphql query, mutation or subscription.

        The results are sent as an ExecutionResult object.
        """

        # Send the query and receive the id
        query_id: int = await self._send_query(
            document, variable_values, operation_name
        )

        # Create a queue to receive the answers for this query_id
        listener = ListenerQueue(query_id, send_stop=(send_stop is True))
        self.listeners[query_id] = listener

        # We will need to wait at close for this query to clean properly
        self._no_more_listeners.clear()

        try:
            # Loop over the received answers
            while True:

                # Wait for the answer from the queue of this query_id
                # This can raise a TransportError or ConnectionClosed exception.
                answer_type, execution_result = await listener.get()

                # If the received answer contains data,
                # Then we will yield the results back as an ExecutionResult object
                if execution_result is not None:
                    yield execution_result

                # If we receive a 'complete' answer from the server,
                # Then we will end this async generator output without errors
                elif answer_type == "complete":
                    log.debug(
                        f"Complete received for query {query_id} --> exit without error"
                    )
                    break

        except (asyncio.CancelledError, GeneratorExit) as e:
            log.debug(f"Exception in subscribe: {e!r}")
            if listener.send_stop:
                await self._stop_listener(query_id)
                listener.send_stop = False

        finally:
            log.debug(f"In subscribe finally for query_id {query_id}")
            self._remove_listener(query_id)
