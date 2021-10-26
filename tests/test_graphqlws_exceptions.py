import asyncio
import json
import types
from typing import List

import pytest

from gql import Client, gql
from gql.transport.exceptions import (
    TransportClosed,
    TransportProtocolError,
    TransportQueryError,
)

from .conftest import WebSocketServerHelper

# Marking all tests in this file with the websockets marker
pytestmark = pytest.mark.websockets

invalid_query_str = """
    query getContinents {
      continents {
        code
        bloh
      }
    }
"""

invalid_query1_server_answer = (
    '{{"type":"next","id":"{query_id}",'
    '"payload":{{"errors":['
    '{{"message":"Cannot query field \\"bloh\\" on type \\"Continent\\".",'
    '"locations":[{{"line":4,"column":5}}],'
    '"extensions":{{"code":"INTERNAL_SERVER_ERROR"}}}}]}}}}'
)

invalid_query1_server = [invalid_query1_server_answer]


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [invalid_query1_server], indirect=True)
@pytest.mark.parametrize("query_str", [invalid_query_str])
async def test_graphqlws_invalid_query(
    event_loop, client_and_graphqlws_server, query_str
):

    session, server = client_and_graphqlws_server

    query = gql(query_str)

    with pytest.raises(TransportQueryError) as exc_info:
        await session.execute(query)

    exception = exc_info.value

    assert isinstance(exception.errors, List)

    error = exception.errors[0]

    assert error["extensions"]["code"] == "INTERNAL_SERVER_ERROR"


invalid_subscription_str = """
    subscription getContinents {
      continents {
        code
        bloh
      }
    }
"""


async def server_invalid_subscription(ws, path):
    await WebSocketServerHelper.send_connection_ack(ws)
    await ws.recv()
    await ws.send(invalid_query1_server_answer.format(query_id=1))
    await WebSocketServerHelper.send_complete(ws, 1)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "graphqlws_server", [server_invalid_subscription], indirect=True
)
@pytest.mark.parametrize("query_str", [invalid_subscription_str])
async def test_graphqlws_invalid_subscription(
    event_loop, client_and_graphqlws_server, query_str
):

    session, server = client_and_graphqlws_server

    query = gql(query_str)

    with pytest.raises(TransportQueryError) as exc_info:
        async for result in session.subscribe(query):
            pass

    exception = exc_info.value

    assert isinstance(exception.errors, List)

    error = exception.errors[0]

    assert error["extensions"]["code"] == "INTERNAL_SERVER_ERROR"


async def server_no_ack(ws, path):
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_no_ack], indirect=True)
@pytest.mark.parametrize("query_str", [invalid_query_str])
async def test_graphqlws_server_does_not_send_ack(
    event_loop, graphqlws_server, query_str
):
    from gql.transport.websockets import WebsocketsTransport

    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}/graphql"

    sample_transport = WebsocketsTransport(url=url, ack_timeout=1)

    with pytest.raises(asyncio.TimeoutError):
        async with Client(transport=sample_transport):
            pass


invalid_payload_server_answer = (
    '{"type":"error","id":"1","payload":{"message":"Must provide document"}}'
)


async def server_invalid_payload(ws, path):
    await WebSocketServerHelper.send_connection_ack(ws)
    result = await ws.recv()
    print(f"Server received: {result}")
    await ws.send(invalid_payload_server_answer)
    await WebSocketServerHelper.wait_connection_terminate(ws)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_invalid_payload], indirect=True)
@pytest.mark.parametrize("query_str", [invalid_query_str])
async def test_graphqlws_sending_invalid_payload(
    event_loop, client_and_graphqlws_server, query_str
):

    session, server = client_and_graphqlws_server

    # Monkey patching the _send_query method to send an invalid payload

    async def monkey_patch_send_query(
        self, document, variable_values=None, operation_name=None,
    ) -> int:
        query_id = self.next_query_id
        self.next_query_id += 1

        query_str = json.dumps(
            {"id": str(query_id), "type": "subscribe", "payload": "BLAHBLAH"}
        )

        await self._send(query_str)
        return query_id

    session.transport._send_query = types.MethodType(
        monkey_patch_send_query, session.transport
    )

    query = gql(query_str)

    with pytest.raises(TransportQueryError) as exc_info:
        await session.execute(query)

    exception = exc_info.value

    assert isinstance(exception.errors, List)

    error = exception.errors[0]

    assert error["message"] == "Must provide document"


not_json_answer = ["BLAHBLAH"]
missing_type_answer = ["{}"]
missing_id_answer_1 = ['{"type": "next"}']
missing_id_answer_2 = ['{"type": "error"}']
missing_id_answer_3 = ['{"type": "complete"}']
data_without_payload = ['{"type": "next", "id":"1"}']
error_without_payload = ['{"type": "error", "id":"1"}']
payload_is_not_a_dict = ['{"type": "next", "id":"1", "payload": "BLAH"}']
empty_payload = ['{"type": "next", "id":"1", "payload": {}}']
sending_bytes = [b"\x01\x02\x03"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "graphqlws_server",
    [
        not_json_answer,
        missing_type_answer,
        missing_id_answer_1,
        missing_id_answer_2,
        missing_id_answer_3,
        data_without_payload,
        error_without_payload,
        payload_is_not_a_dict,
        empty_payload,
        sending_bytes,
    ],
    indirect=True,
)
async def test_graphqlws_transport_protocol_errors(
    event_loop, client_and_graphqlws_server
):

    session, server = client_and_graphqlws_server

    query = gql("query { hello }")

    with pytest.raises(TransportProtocolError):
        await session.execute(query)


async def server_without_ack(ws, path):
    # Sending something else than an ack
    await WebSocketServerHelper.send_complete(ws, 1)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_without_ack], indirect=True)
async def test_graphqlws_server_does_not_ack(event_loop, graphqlws_server):
    from gql.transport.websockets import WebsocketsTransport

    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}/graphql"
    print(f"url = {url}")

    sample_transport = WebsocketsTransport(url=url)

    with pytest.raises(TransportProtocolError):
        async with Client(transport=sample_transport):
            pass


async def server_closing_directly(ws, path):
    await ws.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_closing_directly], indirect=True)
async def test_graphqlws_server_closing_directly(event_loop, graphqlws_server):
    import websockets
    from gql.transport.websockets import WebsocketsTransport

    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}/graphql"
    print(f"url = {url}")

    sample_transport = WebsocketsTransport(url=url)

    with pytest.raises(websockets.exceptions.ConnectionClosed):
        async with Client(transport=sample_transport):
            pass


async def server_closing_after_ack(ws, path):
    await WebSocketServerHelper.send_connection_ack(ws)
    await ws.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_closing_after_ack], indirect=True)
async def test_graphqlws_server_closing_after_ack(
    event_loop, client_and_graphqlws_server
):

    import websockets

    session, server = client_and_graphqlws_server

    query = gql("query { hello }")

    with pytest.raises(websockets.exceptions.ConnectionClosed):
        await session.execute(query)

    await session.transport.wait_closed()

    with pytest.raises(TransportClosed):
        await session.execute(query)
