import asyncio
import json
import logging
from contextlib import suppress
from ssl import SSLContext
from typing import Any, AsyncGenerator, Dict, Optional, Tuple, Union, cast

import websockets
from graphql import DocumentNode, ExecutionResult, print_ast
from websockets.client import WebSocketClientProtocol
from websockets.datastructures import HeadersLike
from websockets.exceptions import ConnectionClosed
from websockets.typing import Data, Subprotocol

from .async_transport import AsyncTransport
from .exceptions import (
    TransportAlreadyConnected,
    TransportClosed,
    TransportProtocolError,
    TransportQueryError,
    TransportServerError,
)

log = logging.getLogger(__name__)

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


class WebsocketsTransport(AsyncTransport):
    """:ref:`Async Transport <async_transports>` used to execute GraphQL queries on
    remote servers with websocket connection.

    This transport uses asyncio and the websockets library in order to send requests
    on a websocket connection.
    """

    # This transport supports two subprotocols and will autodetect the
    # subprotocol supported on the server
    APOLLO_SUBPROTOCOL = cast(Subprotocol, "graphql-ws")
    GRAPHQLWS_SUBPROTOCOL = cast(Subprotocol, "graphql-transport-ws")

    def __init__(
        self,
        url: str,
        headers: Optional[HeadersLike] = None,
        ssl: Union[SSLContext, bool] = False,
        init_payload: Dict[str, Any] = {},
        connect_timeout: Optional[Union[int, float]] = 10,
        close_timeout: Optional[Union[int, float]] = 10,
        ack_timeout: Optional[Union[int, float]] = 10,
        keep_alive_timeout: Optional[Union[int, float]] = None,
        ping_interval: Optional[Union[int, float]] = None,
        pong_timeout: Optional[Union[int, float]] = None,
        answer_pings: bool = True,
        connect_args: Dict[str, Any] = {},
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
            we don't send pings.
        :param pong_timeout: Delay in seconds to receive a pong from the backend
            after we sent a ping (only for the graphql-ws protocol).
            By default equal to half of the ping_interval.
        :param answer_pings: Whether the client answers the pings from the backend
            (for the graphql-ws protocol).
            By default: True
        :param connect_args: Other parameters forwarded to websockets.connect
        """

        self.url: str = url
        self.ssl: Union[SSLContext, bool] = ssl
        self.headers: Optional[HeadersLike] = headers
        self.init_payload: Dict[str, Any] = init_payload

        self.connect_timeout: Optional[Union[int, float]] = connect_timeout
        self.close_timeout: Optional[Union[int, float]] = close_timeout
        self.ack_timeout: Optional[Union[int, float]] = ack_timeout
        self.keep_alive_timeout: Optional[Union[int, float]] = keep_alive_timeout
        self.ping_interval: Optional[Union[int, float]] = ping_interval
        self.pong_timeout: Optional[Union[int, float]]
        self.answer_pings: bool = answer_pings

        if ping_interval is not None:
            if pong_timeout is None:
                self.pong_timeout = ping_interval / 2
            else:
                self.pong_timeout = pong_timeout

        self.connect_args = connect_args

        self.websocket: Optional[WebSocketClientProtocol] = None
        self.next_query_id: int = 1
        self.listeners: Dict[int, ListenerQueue] = {}

        self.receive_data_task: Optional[asyncio.Future] = None
        self.check_keep_alive_task: Optional[asyncio.Future] = None
        self.send_ping_task: Optional[asyncio.Future] = None
        self.close_task: Optional[asyncio.Future] = None

        # We need to set an event loop here if there is none
        # Or else we will not be able to create an asyncio.Event()
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

        self._wait_closed: asyncio.Event = asyncio.Event()
        self._wait_closed.set()

        self._no_more_listeners: asyncio.Event = asyncio.Event()
        self._no_more_listeners.set()

        if self.keep_alive_timeout is not None:
            self._next_keep_alive_message: asyncio.Event = asyncio.Event()
            self._next_keep_alive_message.set()

        self.ping_received: asyncio.Event = asyncio.Event()
        """ping_received is an asyncio Event which will fire  each time
        a ping is received with the graphql-ws protocol"""

        self.pong_received: asyncio.Event = asyncio.Event()
        """pong_received is an asyncio Event which will fire  each time
        a pong is received with the graphql-ws protocol"""

        self.payloads: Dict[str, Any] = {}
        """payloads is a dict which will contain the payloads received
        with the graphql-ws protocol.
        Possible keys are: 'ping', 'pong', 'connection_ack'"""

        self._connecting: bool = False

        self.close_exception: Optional[Exception] = None

        self.supported_subprotocols = [
            self.GRAPHQLWS_SUBPROTOCOL,
            self.APOLLO_SUBPROTOCOL,
        ]

    async def _send(self, message: str) -> None:
        """Send the provided message to the websocket connection and log the message"""

        if not self.websocket:
            raise TransportClosed(
                "Transport is not connected"
            ) from self.close_exception

        try:
            await self.websocket.send(message)
            log.info(">>> %s", message)
        except ConnectionClosed as e:
            await self._fail(e, clean_close=False)
            raise e

    async def _receive(self) -> str:
        """Wait the next message from the websocket connection and log the answer"""

        # It is possible that the websocket has been already closed in another task
        if self.websocket is None:
            raise TransportClosed("Transport is already closed")

        # Wait for the next websocket frame. Can raise ConnectionClosed
        data: Data = await self.websocket.recv()

        # websocket.recv() can return either str or bytes
        # In our case, we should receive only str here
        if not isinstance(data, str):
            raise TransportProtocolError("Binary data received in the websocket")

        answer: str = data

        log.info("<<< %s", answer)

        return answer

    async def _wait_ack(self) -> None:
        """Wait for the connection_ack message. Keep alive messages are ignored"""

        while True:
            init_answer = await self._receive()

            answer_type, answer_id, execution_result = self._parse_answer(init_answer)

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

        init_message = json.dumps(
            {"type": "connection_init", "payload": self.init_payload}
        )

        await self._send(init_message)

        # Wait for the connection_ack message or raise a TimeoutError
        await asyncio.wait_for(self._wait_ack(), self.ack_timeout)

    async def send_ping(self, payload: Optional[Any] = None) -> None:
        """Send a ping message for the graphql-ws protocol
        """

        ping_message = {"type": "ping"}

        if payload is not None:
            ping_message["payload"] = payload

        await self._send(json.dumps(ping_message))

    async def send_pong(self, payload: Optional[Any] = None) -> None:
        """Send a pong message for the graphql-ws protocol
        """

        pong_message = {"type": "pong"}

        if payload is not None:
            pong_message["payload"] = payload

        await self._send(json.dumps(pong_message))

    async def _send_stop_message(self, query_id: int) -> None:
        """Send stop message to the provided websocket connection and query_id.

        The server should afterwards return a 'complete' message.
        """

        stop_message = json.dumps({"id": str(query_id), "type": "stop"})

        await self._send(stop_message)

    async def _send_complete_message(self, query_id: int) -> None:
        """Send a complete message for the provided query_id.

        This is only for the graphql-ws protocol.
        """

        complete_message = json.dumps({"id": str(query_id), "type": "complete"})

        await self._send(complete_message)

    async def _stop_listener(self, query_id: int) -> None:
        """Stop the listener corresponding to the query_id depending on the
        detected backend protocol.

        For apollo: send a "stop" message
                    (a "complete" message will be sent from the backend)

        For graphql-ws: send a "complete" message and simulate the reception
                        of a "complete" message from the backend
        """
        if self.subprotocol == self.GRAPHQLWS_SUBPROTOCOL:
            await self._send_complete_message(query_id)
            await self.listeners[query_id].put(("complete", None))
        else:
            await self._send_stop_message(query_id)

    async def _send_connection_terminate_message(self) -> None:
        """Send a connection_terminate message to the provided websocket connection.

        This message indicates that the connection will disconnect.
        """

        connection_terminate_message = json.dumps({"type": "connection_terminate"})

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

        query_str = json.dumps(
            {"id": str(query_id), "type": query_type, "payload": payload}
        )

        await self._send(query_str)

        return query_id

    def _parse_answer_graphqlws(
        self, answer: str
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
        """

        answer_type: str = ""
        answer_id: Optional[int] = None
        execution_result: Optional[ExecutionResult] = None

        try:
            json_answer = json.loads(answer)

            answer_type = str(json_answer.get("type"))

            if answer_type in ["next", "error", "complete"]:
                answer_id = int(str(json_answer.get("id")))

                if answer_type == "next" or answer_type == "error":

                    payload = json_answer.get("payload")

                    if not isinstance(payload, dict):
                        raise ValueError("payload is not a dict")

                    if answer_type == "next":

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

                        raise TransportQueryError(
                            str(payload), query_id=answer_id, errors=[payload]
                        )

            elif answer_type in ["ping", "pong", "connection_ack"]:
                self.payloads[answer_type] = json_answer.get("payload", None)

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
        self, answer: str
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
            json_answer = json.loads(answer)

            answer_type = str(json_answer.get("type"))

            if answer_type in ["data", "error", "complete"]:
                answer_id = int(str(json_answer.get("id")))

                if answer_type == "data" or answer_type == "error":

                    payload = json_answer.get("payload")

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
                error_payload = json_answer.get("payload")
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
        if self.subprotocol == self.GRAPHQLWS_SUBPROTOCOL:
            return self._parse_answer_graphqlws(answer)

        return self._parse_answer_apollo(answer)

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

    async def _receive_data_loop(self) -> None:
        try:
            while True:

                # Wait the next answer from the websocket server
                try:
                    answer = await self._receive()
                except (ConnectionClosed, TransportProtocolError) as e:
                    await self._fail(e, clean_close=False)
                    break
                except TransportClosed:
                    break

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

            # Note: we need to run generator.aclose() here or the finally block in
            # the subscribe will not be reached in pypy3 (python version 3.6.1)
            await generator.aclose()

            break

        if first_result is None:
            raise TransportQueryError(
                "Query completed without any answer received from the server"
            )

        return first_result

    async def connect(self) -> None:
        """Coroutine which will:

        - connect to the websocket address
        - send the init message
        - wait for the connection acknowledge from the server
        - create an asyncio task which will be used to receive
          and parse the websocket answers

        Should be cleaned with a call to the close coroutine
        """

        log.debug("connect: starting")

        if self.websocket is None and not self._connecting:

            # Set connecting to True to avoid a race condition if user is trying
            # to connect twice using the same client at the same time
            self._connecting = True

            # If the ssl parameter is not provided,
            # generate the ssl value depending on the url
            ssl: Optional[Union[SSLContext, bool]]
            if self.ssl:
                ssl = self.ssl
            else:
                ssl = True if self.url.startswith("wss") else None

            # Set default arguments used in the websockets.connect call
            connect_args: Dict[str, Any] = {
                "ssl": ssl,
                "extra_headers": self.headers,
                "subprotocols": self.supported_subprotocols,
            }

            # Adding custom parameters passed from init
            connect_args.update(self.connect_args)

            # Connection to the specified url
            # Generate a TimeoutError if taking more than connect_timeout seconds
            # Set the _connecting flag to False after in all cases
            try:
                self.websocket = await asyncio.wait_for(
                    websockets.client.connect(self.url, **connect_args),
                    self.connect_timeout,
                )
            finally:
                self._connecting = False

            self.websocket = cast(WebSocketClientProtocol, self.websocket)

            # Find the backend subprotocol returned in the response headers
            response_headers = self.websocket.response_headers
            try:
                self.subprotocol = response_headers["Sec-WebSocket-Protocol"]
            except KeyError:
                # If the server does not send the subprotocol header, using
                # the apollo subprotocol by default
                self.subprotocol = self.APOLLO_SUBPROTOCOL

            log.debug(f"backend subprotocol returned: {self.subprotocol!r}")

            self.next_query_id = 1
            self.close_exception = None
            self._wait_closed.clear()

            # Send the init message and wait for the ack from the server
            # Note: This will generate a TimeoutError
            # if no ACKs are received within the ack_timeout
            try:
                await self._send_init_message_and_wait_ack()
            except ConnectionClosed as e:
                raise e
            except (TransportProtocolError, asyncio.TimeoutError) as e:
                await self._fail(e, clean_close=False)
                raise e

            # If specified, create a task to check liveness of the connection
            # through keep-alive messages
            if self.keep_alive_timeout is not None:
                self.check_keep_alive_task = asyncio.ensure_future(
                    self._check_ws_liveness()
                )

            # If requested, create a task to send periodic pings to the backend
            if (
                self.subprotocol == self.GRAPHQLWS_SUBPROTOCOL
                and self.ping_interval is not None
            ):

                self.send_ping_task = asyncio.ensure_future(self._send_ping_coro())

            # Create a task to listen to the incoming websocket messages
            self.receive_data_task = asyncio.ensure_future(self._receive_data_loop())

        else:
            raise TransportAlreadyConnected("Transport is already connected")

        log.debug("connect: done")

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

    async def _clean_close(self, e: Exception) -> None:
        """Coroutine which will:

        - send stop messages for each active subscription to the server
        - send the connection terminate message
        """

        # Send 'stop' message for all current queries
        for query_id, listener in self.listeners.items():

            if listener.send_stop:
                await self._stop_listener(query_id)
                listener.send_stop = False

        # Wait that there is no more listeners (we received 'complete' for all queries)
        try:
            await asyncio.wait_for(self._no_more_listeners.wait(), self.close_timeout)
        except asyncio.TimeoutError:  # pragma: no cover
            log.debug("Timer close_timeout fired")

        if self.subprotocol == self.APOLLO_SUBPROTOCOL:
            # Finally send the 'connection_terminate' message
            await self._send_connection_terminate_message()

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

            # We should always have an active websocket connection here
            assert self.websocket is not None

            # Properly shut down liveness checker if enabled
            if self.check_keep_alive_task is not None:
                # More info: https://stackoverflow.com/a/43810272/1113207
                self.check_keep_alive_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self.check_keep_alive_task

            # Properly shut down the send ping task if enabled
            if self.send_ping_task is not None:
                self.send_ping_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self.send_ping_task

            # Saving exception to raise it later if trying to use the transport
            # after it has already closed.
            self.close_exception = e

            if clean_close:
                log.debug("_close_coro: starting clean_close")
                try:
                    await self._clean_close(e)
                except Exception as exc:  # pragma: no cover
                    log.warning("Ignoring exception in _clean_close: " + repr(exc))

            log.debug("_close_coro: sending exception to listeners")

            # Send an exception to all remaining listeners
            for query_id, listener in self.listeners.items():
                await listener.set_exception(e)

            log.debug("_close_coro: close websocket connection")

            await self.websocket.close()

            log.debug("_close_coro: websocket connection closed")

        except Exception as exc:  # pragma: no cover
            log.warning("Exception catched in _close_coro: " + repr(exc))

        finally:

            log.debug("_close_coro: start cleanup")

            self.websocket = None
            self.close_task = None
            self.check_keep_alive_task = None
            self.send_ping_task = None

            self._wait_closed.set()

        log.debug("_close_coro: exiting")

    async def _fail(self, e: Exception, clean_close: bool = True) -> None:
        log.debug("_fail: starting with exception: " + repr(e))

        if self.close_task is None:

            if self.websocket is None:
                log.debug("_fail started with self.websocket == None -> already closed")
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

        await self._wait_closed.wait()

        log.debug("wait_close: done")
