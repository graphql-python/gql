from __future__ import absolute_import

import websockets
from websockets.http import HeadersLike
from websockets.typing import Data, Subprotocol
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosedOK, ConnectionClosed

from ssl import SSLContext

import asyncio
import json
import logging

from typing import cast, Dict, Optional, Tuple, Union, AsyncGenerator

from graphql.execution import ExecutionResult
from graphql.language.ast import Document
from graphql.language.printer import print_ast

from .async_transport import AsyncTransport

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


class WebsocketsTransport(AsyncTransport):
    """Transport to execute GraphQL queries on remote servers with a websocket connection.

    This transport use asyncio
    The transport uses the websockets library in order to send requests on a websocket connection.

    See README.md for Usage
    """

    def __init__(
        self,
        url: str,
        headers: Optional[HeadersLike] = None,
        ssl: Union[SSLContext, bool] = False,
    ) -> None:
        """Initialize the transport with the given request parameters.

        :param url: The GraphQL server URL. Example: 'wss://server.com:PORT/graphql'.
        :param headers: Dict of HTTP Headers.
        :param ssl: ssl_context of the connection. Use ssl=False to disable encryption
        """
        self.url: str = url
        self.ssl: Union[SSLContext, bool] = ssl
        self.headers: Optional[HeadersLike] = headers

        self.websocket: Optional[WebSocketClientProtocol] = None
        self.next_query_id: int = 1
        self.listeners: Dict[int, ListenerQueue] = {}
        self._is_closing: bool = False
        self._no_more_listeners: asyncio.Event = asyncio.Event()

    async def _send(self, message: str) -> None:
        """Send the provided message to the websocket connection and log the message
        """

        if not self.websocket:
            raise Exception("Transport is not connected")

        try:
            await self.websocket.send(message)
            log.info(">>> %s", message)
        except (ConnectionClosed) as e:
            await self._close_with_exception(e)
            raise e

    async def _receive(self) -> str:
        """Wait the next message from the websocket connection and log the answer
        """

        answer: Optional[str] = None

        if not self.websocket:
            raise Exception("Transport is not connected")

        try:
            data: Data = await self.websocket.recv()

            # websocket.recv() can return either str or bytes
            # In our case, we should receive only str here
            if not isinstance(data, str):
                raise Exception("Binary data received in the websocket")

            answer = data

            log.info("<<< %s", answer)
        except ConnectionClosed as e:
            await self._close_with_exception(e)
            raise e

        return answer

    async def _send_init_message_and_wait_ack(self) -> None:
        """Send an init message to the provided websocket then wait for the connection ack

        If the answer is not a connection_ack message, we will return an Exception
        """

        await self._send('{"type":"connection_init","payload":{}}')

        init_answer = await self._receive()

        answer_type, answer_id, execution_result = self._parse_answer(init_answer)

        if answer_type != "connection_ack":
            raise Exception("Websocket server did not return a connection ack")

    async def _send_stop_message(self, query_id: int) -> None:
        """Send a stop message to the provided websocket connection for the provided query_id

        The server should afterwards return a 'complete' message
        """

        stop_message = json.dumps({"id": str(query_id), "type": "stop"})

        await self._send(stop_message)

    async def _send_connection_terminate_message(self) -> None:
        """Send a connection_terminate message to the provided websocket connection

        This message indicate that the connection will disconnect
        """

        connection_terminate_message = json.dumps({"type": "connection_terminate"})

        await self._send(connection_terminate_message)

    async def _send_query(
        self,
        document: Document,
        variable_values: Optional[Dict[str, str]] = None,
        operation_name: Optional[str] = None,
    ) -> int:
        """Send a query to the provided websocket connection

        We use an incremented id to reference the query

        Returns the used id for this query
        """

        query_id = self.next_query_id
        self.next_query_id += 1

        query_str = json.dumps(
            {
                "id": str(query_id),
                "type": "start",
                "payload": {
                    "variables": variable_values or {},
                    "operationName": operation_name or "",
                    "query": print_ast(document),
                },
            }
        )

        await self._send(query_str)

        return query_id

    def _parse_answer(
        self, answer: str
    ) -> Tuple[str, Optional[int], Optional[ExecutionResult]]:
        """Parse the answer received from the server

        Returns a list consisting of:
            - the answer_type (between: 'connection_ack', 'ka', 'connection_error', 'data', 'error', 'complete')
            - the answer id (Integer) if received or None
            - an execution Result if the answer_type is 'data' or None
        """

        answer_type: str = ""
        answer_id: Optional[int] = None
        execution_result: Optional[ExecutionResult] = None

        try:
            json_answer = json.loads(answer)

            if not isinstance(json_answer, dict):
                raise ValueError

            answer_type = str(json_answer.get("type"))

            if answer_type in ["data", "error", "complete"]:
                answer_id = int(str(json_answer.get("id")))

                if answer_type == "data":
                    result = json_answer.get("payload")

                    if not isinstance(result, Dict):
                        raise ValueError

                    if "errors" not in result and "data" not in result:
                        raise ValueError

                    execution_result = ExecutionResult(
                        errors=result.get("errors"), data=result.get("data")
                    )

                elif answer_type == "error":
                    raise Exception("Websocket server error")

            elif answer_type == "ka":
                # KeepAlive message
                pass
            elif answer_type == "connection_ack":
                pass
            elif answer_type == "connection_error":
                raise Exception("Websocket Connection Error")
            else:
                raise ValueError

        except ValueError:
            raise Exception("Websocket server did not return a GraphQL result")

        return (answer_type, answer_id, execution_result)

    async def _answer_loop(self) -> None:

        while True:

            # Wait the next answer from the websocket server
            try:
                answer = await self._receive()
            except ConnectionClosed:
                return

            # Parse the answer
            answer_type, answer_id, execution_result = self._parse_answer(answer)

            # Continue if no listener exists for this id
            if answer_id not in self.listeners:
                continue

            # Put the answer in the queue
            await self.listeners[answer_id].put((answer_type, execution_result))

    async def subscribe(
        self,
        document: Document,
        variable_values: Optional[Dict[str, str]] = None,
        operation_name: Optional[str] = None,
        send_stop: Optional[bool] = True,
    ) -> AsyncGenerator[ExecutionResult, None]:
        """Send a query and receive the results using a python async generator

        The query can be a graphql query, mutation or subscription

        The results are sent as an ExecutionResult object
        """

        # Send the query and receive the id
        query_id: int = await self._send_query(
            document, variable_values, operation_name
        )

        # Create a queue to receive the answers for this query_id
        listener = ListenerQueue(query_id, send_stop=(send_stop is True))
        self.listeners[query_id] = listener

        try:
            # Loop over the received answers
            while True:

                # Wait for the answer from the queue of this query_id
                answer_type, execution_result = await listener.get()

                # If the received answer contains data,
                #     Then we will yield the results back as an ExecutionResult object
                if execution_result is not None:
                    yield execution_result

                # If we receive a 'complete' answer from the server,
                #     Then we will end this async generator output and disconnect from the server
                elif answer_type == "complete":
                    log.debug(
                        f"Complete received for query {query_id} --> exit without error"
                    )
                    break

        except (asyncio.CancelledError, GeneratorExit) as e:
            log.debug("Exception in subscribe: " + repr(e))
            if listener.send_stop:
                await self._send_stop_message(query_id)
                listener.send_stop = False

        finally:
            del self.listeners[query_id]
            if len(self.listeners) == 0:
                self._no_more_listeners.set()

    async def execute(
        self,
        document: Document,
        variable_values: Optional[Dict[str, str]] = None,
        operation_name: Optional[str] = None,
    ) -> ExecutionResult:
        """Send a query but close the async generator as soon as we have the first answer

        The result is sent as an ExecutionResult object
        """
        async for result in self.subscribe(
            document, variable_values, operation_name, send_stop=False
        ):
            first_result = result

        return first_result

    async def connect(self) -> None:
        """Coroutine which will:

        - connect to the websocket address
        - send the init message
        - wait for the connection acknowledge from the server
        - create an asyncio task which will be used to receive and parse the websocket answers

        Should be cleaned with a call to the close coroutine
        """

        GRAPHQLWS_SUBPROTOCOL: Subprotocol = cast(Subprotocol, "graphql-ws")

        if self.websocket is None:

            # Connection to the specified url
            self.websocket = await websockets.connect(
                self.url,
                ssl=self.ssl if self.ssl else None,
                extra_headers=self.headers,
                subprotocols=[GRAPHQLWS_SUBPROTOCOL],
            )

            # Reset the next query id
            self.next_query_id = 1

            # Send the init message and wait for the ack from the server
            await self._send_init_message_and_wait_ack()

            # Create a task to listen to the incoming websocket messages
            self.listen_loop = asyncio.ensure_future(self._answer_loop())

    async def close(self) -> None:
        """Coroutine which will:

        - send stop messages for each active query to the server
        - send the connection terminate message
        - close the websocket connection

        - send the exceptions to all current listeners
        - remove the listen_loop task
        """
        if self.websocket and not self._is_closing:

            # Send stop message for all current queries
            for query_id, listener in self.listeners.items():

                if listener.send_stop:
                    await self._send_stop_message(query_id)
                    listener.send_stop = False

            # Wait that there is no more listeners (we received 'complete' for all queries)
            await asyncio.wait_for(self._no_more_listeners.wait(), timeout=5)

            await self._send_connection_terminate_message()

            await self.websocket.close()

            await self._close_with_exception(
                ConnectionClosedOK(
                    code=1000, reason="Websocket GraphQL transport closed by user"
                )
            )

    async def _close_with_exception(self, e: Exception) -> None:
        """Coroutine called to close the transport if the underlaying websocket transport
        has closed itself

        - send the exceptions to all current listeners
        - remove the listen_loop task
        """
        if self.websocket and not self._is_closing:

            self._is_closing = True

            for query_id, listener in self.listeners.items():

                await listener.set_exception(e)

            self.websocket = None

            self.listen_loop.cancel()
