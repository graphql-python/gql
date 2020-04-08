import asyncio
import pytest
import websockets

from .websocket_fixtures import server, client_and_server, TestServer
from graphql.execution import ExecutionResult
from gql.transport.websockets import WebsocketsTransport
from gql import gql, AsyncClient
from typing import Dict


query1_str = """
    query getContinents {
      continents {
        code
        name
      }
    }
"""

query1_server_answer = (
    '{{"type":"data","id":"{query_id}","payload":{{"data":{{"continents":['
    '{{"code":"AF","name":"Africa"}},{{"code":"AN","name":"Antarctica"}},{{"code":"AS","name":"Asia"}},'
    '{{"code":"EU","name":"Europe"}},{{"code":"NA","name":"North America"}},{{"code":"OC","name":"Oceania"}},'
    '{{"code":"SA","name":"South America"}}]}}}}}}'
)


async def server1(ws, path):
    await TestServer.send_connection_ack(ws)
    result = await ws.recv()
    print(f"Server received: {result}")
    await ws.send(query1_server_answer.format(query_id=1))
    await TestServer.send_complete(ws, 1)
    await TestServer.wait_connection_terminate(ws)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server1], indirect=True)
async def test_websocket_starting_client_in_context_manager(server):

    url = "ws://" + server.hostname + ":" + str(server.port) + "/graphql"
    print(f"url = {url}")

    sample_transport = WebsocketsTransport(url=url)

    async with AsyncClient(transport=sample_transport) as client:

        assert isinstance(
            sample_transport.websocket, websockets.client.WebSocketClientProtocol
        )

        query1 = gql(query1_str)

        result = await client.execute(query1)

        assert isinstance(result, ExecutionResult)

        print("Client received: " + str(result.data))

        # Verify result
        assert result.errors is None
        assert isinstance(result.data, Dict)

        continents = result.data["continents"]
        africa = continents[0]

        assert africa["code"] == "AF"

    # Check client is disconnect here
    assert sample_transport.websocket is None


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server1], indirect=True)
@pytest.mark.parametrize("query_str", [query1_str])
async def test_websocket_simple_query(client_and_server, query_str):

    client, server = client_and_server

    query = gql(query_str)

    result = await client.execute(query)

    print("Client received: " + str(result.data))


async def server1_two_queries_in_series(ws, path):
    await TestServer.send_connection_ack(ws)
    result = await ws.recv()
    print(f"Server received: {result}")
    await ws.send(query1_server_answer.format(query_id=1))
    await TestServer.send_complete(ws, 1)
    result = await ws.recv()
    print(f"Server received: {result}")
    await ws.send(query1_server_answer.format(query_id=2))
    await TestServer.send_complete(ws, 2)
    await TestServer.wait_connection_terminate(ws)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server1_two_queries_in_series], indirect=True)
@pytest.mark.parametrize("query_str", [query1_str])
async def test_websocket_two_queries_in_series(client_and_server, query_str):

    client, server = client_and_server

    query = gql(query_str)

    result1 = await client.execute(query)

    print("Query1 received: " + str(result1.data))

    result2 = await client.execute(query)

    print("Query2 received: " + str(result2.data))

    assert str(result1.data) == str(result2.data)


async def server1_two_queries_in_parallel(ws, path):
    await TestServer.send_connection_ack(ws)
    result = await ws.recv()
    print(f"Server received: {result}")
    result = await ws.recv()
    print(f"Server received: {result}")
    await ws.send(query1_server_answer.format(query_id=1))
    await ws.send(query1_server_answer.format(query_id=2))
    await TestServer.send_complete(ws, 1)
    await TestServer.send_complete(ws, 2)
    await TestServer.wait_connection_terminate(ws)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server1_two_queries_in_parallel], indirect=True)
@pytest.mark.parametrize("query_str", [query1_str])
async def test_websocket_two_queries_in_parallel(client_and_server, query_str):

    client, server = client_and_server

    query = gql(query_str)

    result1 = None
    result2 = None

    async def task1_coro():
        nonlocal result1
        result1 = await client.execute(query)

    async def task2_coro():
        nonlocal result2
        result2 = await client.execute(query)

    task1 = asyncio.ensure_future(task1_coro())
    task2 = asyncio.ensure_future(task2_coro())

    await asyncio.gather(task1, task2)

    print("Query1 received: " + str(result1.data))
    print("Query2 received: " + str(result2.data))

    assert str(result1.data) == str(result2.data)
