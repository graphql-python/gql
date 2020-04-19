import asyncio
import pytest
import json
import websockets
import types
import gql

from parse import search
from .websocket_fixtures import MS, server, client_and_server, TestServer
from graphql.execution import ExecutionResult
from gql import gql, AsyncClient
from gql.transport.websockets import WebsocketsTransport
from gql.transport.exceptions import (
    TransportProtocolError,
    TransportQueryError,
    TransportServerError,
    TransportClosed,
)


invalid_query_str = """
    query getContinents {
      continents {
        code
        bloh
      }
    }
"""

invalid_query1_server_answer = (
    '{{"type":"data","id":"{query_id}",'
    '"payload":{{"errors":[{{"message":"Cannot query field \\"bloh\\" on type \\"Continent\\".",'
    '"locations":[{{"line":4,"column":5}}],"extensions":{{"code":"INTERNAL_SERVER_ERROR"}}}}]}}}}'
)

invalid_query1_server = [
    invalid_query1_server_answer,
]


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [invalid_query1_server,], indirect=True)
@pytest.mark.parametrize("query_str", [invalid_query_str])
async def test_websocket_invalid_query(client_and_server, query_str):

    client, server = client_and_server

    query = gql(query_str)

    result = await client.execute(query)

    print("Client received: " + str(result.data))

    assert isinstance(result, ExecutionResult)

    print(f"result = {repr(result.data)}, {repr(result.errors)}")

    assert result.data is None
    assert result.errors is not None


connection_error_server_answer = (
    '{"type":"connection_error","id":null,'
    '"payload":{"message":"Unexpected token Q in JSON at position 0"}}'
)


async def server_connection_error(ws, path):
    await TestServer.send_connection_ack(ws)
    result = await ws.recv()
    print(f"Server received: {result}")
    await ws.send(connection_error_server_answer)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_connection_error], indirect=True)
@pytest.mark.parametrize("query_str", [invalid_query_str])
async def test_websocket_sending_invalid_data(client_and_server, query_str):

    client, server = client_and_server

    invalid_data = "QSDF"
    print(f">>> {invalid_data}")
    await client.transport.websocket.send(invalid_data)

    await asyncio.sleep(2 * MS)


invalid_payload_server_answer = (
    '{"type":"error","id":"1","payload":{"message":"Must provide document"}}'
)


async def server_invalid_payload(ws, path):
    await TestServer.send_connection_ack(ws)
    result = await ws.recv()
    print(f"Server received: {result}")
    await ws.send(invalid_payload_server_answer)
    await TestServer.wait_connection_terminate(ws)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_invalid_payload], indirect=True)
@pytest.mark.parametrize("query_str", [invalid_query_str])
async def test_websocket_sending_invalid_payload(client_and_server, query_str):

    client, server = client_and_server

    # Monkey patching the _send_query method to send an invalid payload

    async def monkey_patch_send_query(
        self, document, variable_values=None, operation_name=None,
    ) -> int:
        query_id = self.next_query_id
        self.next_query_id += 1

        query_str = json.dumps(
            {"id": str(query_id), "type": "start", "payload": "BLAHBLAH",}
        )

        await self._send(query_str)
        return query_id

    client.transport._send_query = types.MethodType(
        monkey_patch_send_query, client.transport
    )

    query = gql(query_str)

    with pytest.raises(TransportQueryError):
        result = await client.execute(query)


not_json_answer = ["BLAHBLAH"]
missing_type_answer = ["{}"]
missing_id_answer_1 = ['{"type": "data"}']
missing_id_answer_2 = ['{"type": "error"}']
missing_id_answer_3 = ['{"type": "complete"}']
data_without_payload = ['{"type": "data", "id":"1"}']
error_without_payload = ['{"type": "error", "id":"1"}']
payload_is_not_a_dict = ['{"type": "data", "id":"1", "payload": "BLAH"}']
empty_payload = ['{"type": "data", "id":"1", "payload": {}}']
sending_bytes = [b"\x01\x02\x03"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "server",
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
async def test_websocket_transport_protocol_errors(client_and_server):

    client, server = client_and_server

    query = gql("query { hello }")

    with pytest.raises(TransportProtocolError):
        result = await client.execute(query)


async def server_without_ack(ws, path):
    # Sending something else than an ack
    await TestServer.send_keepalive(ws)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_without_ack,], indirect=True)
async def test_websocket_server_does_not_ack(server):

    url = "ws://" + server.hostname + ":" + str(server.port) + "/graphql"
    print(f"url = {url}")

    sample_transport = WebsocketsTransport(url=url)

    with pytest.raises(TransportProtocolError):
        async with AsyncClient(transport=sample_transport) as client:

            pass


async def server_closing_directly(ws, path):
    await ws.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_closing_directly,], indirect=True)
async def test_websocket_server_closing_directly(server):

    url = "ws://" + server.hostname + ":" + str(server.port) + "/graphql"
    print(f"url = {url}")

    sample_transport = WebsocketsTransport(url=url)

    with pytest.raises(websockets.exceptions.ConnectionClosed):
        async with AsyncClient(transport=sample_transport) as client:

            pass


async def server_closing_after_ack(ws, path):
    await TestServer.send_connection_ack(ws)
    await ws.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_closing_after_ack,], indirect=True)
async def test_websocket_server_closing_after_ack(client_and_server):

    client, server = client_and_server

    query = gql("query { hello }")

    with pytest.raises(websockets.exceptions.ConnectionClosed):
        result = await client.execute(query)

    await client.transport.wait_closed()

    with pytest.raises(TransportClosed):
        result = await client.execute(query)
