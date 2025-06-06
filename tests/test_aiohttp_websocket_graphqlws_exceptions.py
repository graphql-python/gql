import asyncio
from typing import List

import pytest

from gql import Client, gql
from gql.transport.exceptions import (
    TransportConnectionFailed,
    TransportProtocolError,
    TransportQueryError,
)

from .conftest import WebSocketServerHelper

# Marking all tests in this file with the aiohttp AND websockets marker
pytestmark = [pytest.mark.aiohttp, pytest.mark.websockets]

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
async def test_aiohttp_websocket_graphqlws_invalid_query(
    client_and_aiohttp_websocket_graphql_server, query_str
):

    session, server = client_and_aiohttp_websocket_graphql_server

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


async def server_invalid_subscription(ws):
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
async def test_aiohttp_websocket_graphqlws_invalid_subscription(
    client_and_aiohttp_websocket_graphql_server, query_str
):

    session, server = client_and_aiohttp_websocket_graphql_server

    query = gql(query_str)

    with pytest.raises(TransportQueryError) as exc_info:
        async for result in session.subscribe(query):
            pass

    exception = exc_info.value

    assert isinstance(exception.errors, List)

    error = exception.errors[0]

    assert error["extensions"]["code"] == "INTERNAL_SERVER_ERROR"


async def server_no_ack(ws):
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_no_ack], indirect=True)
@pytest.mark.parametrize("query_str", [invalid_query_str])
async def test_aiohttp_websocket_graphqlws_server_does_not_send_ack(
    graphqlws_server, query_str
):
    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}/graphql"

    transport = AIOHTTPWebsocketsTransport(url=url, ack_timeout=0.1)

    with pytest.raises(asyncio.TimeoutError):
        async with Client(transport=transport):
            pass


invalid_query_server_answer = (
    '{"id":"1","type":"error","payload":[{"message":"Cannot query field '
    '\\"helo\\" on type \\"Query\\". Did you mean \\"hello\\"?",'
    '"locations":[{"line":2,"column":3}]}]}'
)


async def server_invalid_query(ws):
    await WebSocketServerHelper.send_connection_ack(ws)
    result = await ws.recv()
    print(f"Server received: {result}")
    await ws.send(invalid_query_server_answer)
    await WebSocketServerHelper.wait_connection_terminate(ws)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_invalid_query], indirect=True)
async def test_aiohttp_websocket_graphqlws_sending_invalid_query(
    client_and_aiohttp_websocket_graphql_server,
):

    session, server = client_and_aiohttp_websocket_graphql_server

    query = gql("{helo}")

    with pytest.raises(TransportQueryError) as exc_info:
        await session.execute(query)

    exception = exc_info.value

    assert isinstance(exception.errors, List)

    error = exception.errors[0]

    assert (
        error["message"]
        == 'Cannot query field "helo" on type "Query". Did you mean "hello"?'
    )


not_json_answer = ["BLAHBLAH"]
missing_type_answer = ["{}"]
missing_id_answer_1 = ['{"type": "next"}']
missing_id_answer_2 = ['{"type": "error"}']
missing_id_answer_3 = ['{"type": "complete"}']
data_without_payload = ['{"type": "next", "id":"1"}']
error_without_payload = ['{"type": "error", "id":"1"}']
error_with_payload_not_a_list = ['{"type": "error", "id":"1", "payload": "NOT A LIST"}']
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
        error_with_payload_not_a_list,
        empty_payload,
        sending_bytes,
    ],
    indirect=True,
)
async def test_aiohttp_websocket_graphqlws_transport_protocol_errors(
    client_and_aiohttp_websocket_graphql_server,
):

    session, server = client_and_aiohttp_websocket_graphql_server

    query = gql("query { hello }")

    with pytest.raises((TransportProtocolError, TransportQueryError)):
        await session.execute(query)


async def server_without_ack(ws):
    # Sending something else than an ack
    await WebSocketServerHelper.send_complete(ws, 1)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_without_ack], indirect=True)
async def test_aiohttp_websocket_graphqlws_server_does_not_ack(graphqlws_server):
    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}/graphql"
    print(f"url = {url}")

    transport = AIOHTTPWebsocketsTransport(url=url)

    with pytest.raises(TransportProtocolError):
        async with Client(transport=transport):
            pass


async def server_closing_directly(ws):
    await ws.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_closing_directly], indirect=True)
async def test_aiohttp_websocket_graphqlws_server_closing_directly(graphqlws_server):

    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}/graphql"
    print(f"url = {url}")

    transport = AIOHTTPWebsocketsTransport(url=url)

    with pytest.raises(TransportConnectionFailed):
        async with Client(transport=transport):
            pass


async def server_closing_after_ack(ws):
    await WebSocketServerHelper.send_connection_ack(ws)
    await ws.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_closing_after_ack], indirect=True)
async def test_aiohttp_websocket_graphqlws_server_closing_after_ack(
    client_and_aiohttp_websocket_graphql_server,
):

    session, _ = client_and_aiohttp_websocket_graphql_server

    query = gql("query { hello }")

    print("\n Trying to execute first query.\n")

    with pytest.raises(TransportConnectionFailed):
        await session.execute(query)

    await session.transport.wait_closed()

    print("\n Trying to execute second query.\n")

    with pytest.raises(TransportConnectionFailed):
        await session.execute(query)
