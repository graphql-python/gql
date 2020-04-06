from __future__ import absolute_import

from typing import Any, Dict, Union

import websockets
import asyncio
import json
import logging

from graphql.execution import ExecutionResult
from graphql.language.ast import Document
from graphql.language.printer import print_ast

from gql.transport import AsyncTransport

log = logging.getLogger(__name__)


class WebsocketsTransport(AsyncTransport):
    """Transport to execute GraphQL queries on remote servers with a websocket connection.

    This transport use asyncio
    The transport uses the websockets library in order to send requests on a websocket connection.

    See README.md for Usage
    """

    def __init__(
        self, url, headers=None, ssl=False,
    ):
        """Initialize the transport with the given request parameters.

        :param url: The GraphQL server URL. Example: 'wss://server.com:PORT/graphql'.
        :param headers: Dict of HTTP Headers.
        :param ssl: ssl_context of the connection. Use ssl=False to disable encryption
        """
        self.url = url
        self.ssl = ssl
        self.headers = headers

        self.websocket = None
        self.next_query_id = 1
        self.listeners = {}
        self._is_closing = False

    async def _send(self, message):
        """Send the provided message to the websocket connection and log the message
        """

        if not self.websocket:
            raise Exception("Transport is not connected")

        try:
            await self.websocket.send(message)
            log.info(">>> %s", message)
        except (websockets.exceptions.ConnectionClosedError) as e:
            await self.close()
            raise e

    async def _receive(self):
        """Wait the next message from the websocket connection and log the answer
        """

        answer = None

        try:
            answer = await self.websocket.recv()
            log.info("<<< %s", answer)
        except websockets.exceptions.ConnectionClosedError as e:
            await self.close()
            raise e

        return answer

    async def _send_init_message_and_wait_ack(self):
        """Send an init message to the provided websocket then wait for the connection ack

        If the answer is not a connection_ack message, we will return an Exception
        """

        await self._send('{"type":"connection_init","payload":{}}')

        init_answer = await self._receive()

        answer_type, answer_id, execution_result = self._parse_answer(init_answer)

        if answer_type != "connection_ack":
            raise Exception("Websocket server did not return a connection ack")

    async def _send_stop_message(self, query_id):
        """Send a stop message to the provided websocket connection for the provided query_id

        The server should afterwards return a 'complete' message
        """

        stop_message = json.dumps({"id": str(query_id), "type": "stop"})

        await self._send(stop_message)

    async def _send_connection_terminate_message(self):
        """Send a connection_terminate message to the provided websocket connection

        This message indicate that the connection will disconnect
        """

        connection_terminate_message = json.dumps({"type": "connection_terminate"})

        await self._send(connection_terminate_message)

    async def _send_query(self, document, variable_values, operation_name):
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
                    #'extensions': {},
                    "operationName": operation_name or "",
                    "query": print_ast(document),
                },
            }
        )

        await self._send(query_str)

        return query_id

    def _parse_answer(self, answer):
        """Parse the answer received from the server

        Returns a list consisting of:
            - the answer_type (between: 'connection_ack', 'ka', 'connection_error', 'data', 'error', 'complete')
            - the answer id (Integer) if received or None
            - an execution Result if the answer_type is 'data' or None
        """

        answer_type = None
        answer_id = None
        execution_result = None

        try:
            json_answer = json.loads(answer)

            if not isinstance(json_answer, dict):
                raise ValueError

            answer_type = json_answer.get("type")

            if answer_type in ["data", "error", "complete"]:
                answer_id = int(json_answer.get("id"))

                if answer_type == "data":
                    result = json_answer.get("payload")

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

    async def _answer_loop(self):

        while True:

            # Wait the next answer from the websocket server
            answer = await self._receive()

            # Parse the answer
            answer_type, answer_id, execution_result = self._parse_answer(answer)

            # Continue if no listener exists for this id
            if answer_id not in self.listeners:
                continue

            # Get the related queue
            queue = self.listeners[answer_id]

            # Put the answer in the queue
            await queue.put((answer_type, execution_result))

    async def subscribe(self, document, variable_values=None, operation_name=None):
        """Send a query and receive the results using a python async generator

        The query can be a graphql query, mutation or subscription

        The results are sent as an ExecutionResult object
        """

        # Send the query and receive the id
        query_id = await self._send_query(document, variable_values, operation_name)

        # Create a queue to receive the answers for this query_id
        self.listeners[query_id] = asyncio.Queue()

        try:
            # Loop over the received answers
            while True:

                # Wait for the answer from the queue of this query_id
                answer_type, execution_result = await self.listeners[query_id].get()

                # Set the task as done in the listeners queue
                self.listeners[query_id].task_done()

                # If the received answer contains data,
                #     Then we will yield the results back as an ExecutionResult object
                if execution_result is not None:
                    yield execution_result

                # If we receive a 'complete' answer from the server,
                #     Then we will end this async generator output and disconnect from the server
                elif answer_type == "complete":
                    break

        except (asyncio.CancelledError, GeneratorExit) as e:
            await self._send_stop_message(query_id)

        finally:
            del self.listeners[query_id]

    async def execute(self, document, variable_values=None, operation_name=None):
        """Send a query but close the async generator as soon as we have the first answer

        The result is sent as an ExecutionResult object
        """
        generator = self.subscribe(document, variable_values, operation_name)

        first_result = None

        async for execution_result in generator:
            first_result = execution_result
            generator.aclose()

        if first_result is None:
            raise asyncio.CancelledError

        return first_result

    async def connect(self):
        """Coroutine which will:

        - connect to the websocket address
        - send the init message
        - wait for the connection acknowledge from the server
        - create an asyncio task which will be used to receive and parse the websocket answers

        Should be cleaned with a call to the close coroutine
        """

        if self.websocket == None:

            # Connection to the specified url
            self.websocket = await websockets.connect(
                self.url,
                ssl=self.ssl,
                extra_headers=self.headers,
                subprotocols=["graphql-ws"],
            )

            # Reset the next query id
            self.next_query_id = 1

            # Send the init message and wait for the ack from the server
            await self._send_init_message_and_wait_ack()

            # Create a task to listen to the incoming websocket messages
            self.listen_loop = asyncio.ensure_future(self._answer_loop())

    async def close(self):
        """Coroutine which will:

        - send the connection terminate message
        - close the websocket connection
        - send 'complete' messages to close all the existing subscribe async generators
        - remove the listen_loop task
        """

        if self.websocket and not self._is_closing:

            self._is_closing = True

            try:
                await self._send_connection_terminate_message()
                await self.websocket.close()
            except websockets.exceptions.ConnectionClosedError:
                pass

            for query_id in self.listeners:
                await self.listeners[query_id].put(("complete", None))

            self.websocket = None

            self.listen_loop.cancel()
