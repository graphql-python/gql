from __future__ import absolute_import

from typing import Any, Dict, Union

import websockets
import asyncio
import json
import logging

from graphql.execution import ExecutionResult
from graphql.language.ast import Document
from graphql.language.printer import print_ast

from gql.transport import Transport

log = logging.getLogger(__name__)

class WebsocketsTransport(Transport):
    """Transport to execute GraphQL queries on remote servers with a websocket connection.

    This transport use asyncio
    The transport uses the websockets library in order to send requests on a websocket connection.

    See README.md for Usage
    """

    USING_ASYNCIO = True

    def __init__(
        self,
        url,
        headers=None,
        ssl=False,
    ):
        """Initialize the transport with the given request parameters.

        :param url: The GraphQL server URL. Example: 'wss://server.com:PORT/graphql'.
        :param headers: Dict of HTTP Headers.
        :param ssl: ssl_context of the connection. Use ssl=False to disable encryption
        """
        self.url = url
        self.ssl = ssl
        self.headers = headers
        self.next_query_id = 1

    async def _send_message(self, websocket, message):
        """Send the provided message to the websocket connection and log the message
        """

        await websocket.send(message)
        log.info('>>> %s', message)

    async def _wait_answer(self, websocket):
        """Wait the next message from the websocket connection and log the answer
        """

        answer = await websocket.recv()
        log.info('<<< %s', answer)

        return answer

    async def _send_init_message_and_wait_ack(self, websocket):
        """Send an init message to the provided websocket then wait for the connection ack

        If the answer is not a connection_ack message, we will return an Exception
        """

        await self._send_message(websocket, '{"type":"connection_init","payload":{}}')

        init_answer = await self._wait_answer(websocket)

        answer_type, answer_id, execution_result = self._parse_answer(init_answer)

        if answer_type != 'connection_ack':
            raise Exception('Websocket server did not return a connection ack')

    async def _send_stop_message(self, websocket, query_id):
        """Send a stop message to the provided websocket connection for the provided query_id

        The server should afterwards return a 'complete' message
        """

        stop_message = json.dumps({
            'id': str(query_id),
            'type': 'stop'
        })

        await self._send_message(websocket, stop_message)

    async def _send_query(self, websocket, document, variable_values, operation_name):
        """Send a query to the provided websocket connection

        We use an incremented id to reference the query

        Returns the used id for this query
        """

        query_id = self.next_query_id
        self.next_query_id += 1

        query_str = json.dumps({
            'id': str(query_id),
            'type': 'start',
            'payload': {
                'variables': variable_values or {},
                #'extensions': {},
                'operationName': operation_name or '',
                'query': print_ast(document)
            }
        })

        await self._send_message(websocket, query_str)

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

            answer_type = json_answer.get('type')

            if answer_type in ['data', 'error', 'complete']:
                answer_id = int(json_answer.get('id'))

                if answer_type == 'data':
                    result = json_answer.get('payload')

                    if 'errors' not in result and 'data' not in result:
                        raise ValueError

                    execution_result = ExecutionResult(errors=result.get('errors'), data=result.get('data'))

                elif answer_type == 'error':
                    raise Exception('Websocket server error')

            elif answer_type == 'ka':
                # KeepAlive message
                pass
            elif answer_type == 'connection_ack':
                pass
            elif answer_type == 'connection_error':
                raise Exception('Websocket Connection Error')
            else:
                raise ValueError

        except ValueError:
            raise Exception('Websocket server did not return a GraphQL result')

        return (answer_type, answer_id, execution_result)


    async def subscribe(self, document, variable_values=None, operation_name=None):
        """Send a query and receive the results using a python async generator

        The query can be a graphql query, mutation or subscription

        The results are sent as an ExecutionResult object
        """

        # Connection to the specified url
        async with websockets.connect(
            self.url,
            ssl=self.ssl,
            extra_headers=self.headers,
            subprotocols=['graphql-ws']
        ) as websocket:

            # Send the init message and wait for the ack from the server
            await self._send_init_message_and_wait_ack(websocket)

            # Send the query and receive the id
            query_id = await self._send_query(websocket, document, variable_values, operation_name)

            # Loop over the received answers
            while True:

                # Wait the next answer from the websocket server
                answer = await self._wait_answer(websocket)

                # Parse the answer
                answer_type, answer_id, execution_result = self._parse_answer(answer)

                # If the received answer id corresponds to the query id,
                #     Then we will yield the results back as an ExecutionResult object
                #     If we receive a 'complete' answer from the server,
                #         Then we will end this async generator output and disconnect from the server
                if answer_id == query_id:
                    if execution_result is not None:
                        yield execution_result

                    elif answer_type == 'complete':
                        return

    async def single_query(self, document, variable_values=None, operation_name=None):
        """Send a query but close the connection as soon as we have the first answer

        The result is sent as an ExecutionResult object
        """
        async for result in self.subscribe(document, variable_values, operation_name):
            return result

    def execute(self, document):
        raise NotImplementedError(
            "You should use the async function 'execute_async' for this transport"
        )
