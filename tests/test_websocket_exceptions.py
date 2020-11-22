import asyncio
import json
import types
from typing import List

import pytest

from gql import Client, gql
from gql.transport.exceptions import (
    TransportAlreadyConnected,
    TransportClosed,
    TransportProtocolError,
    TransportQueryError,
)

from .conftest import MS, WebSocketServerHelper

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
    '{{"type":"data","id":"{query_id}",'
    '"payload":{{"errors":['
    '{{"message":"Cannot query field \\"bloh\\" on type \\"Continent\\".",'
    '"locations":[{{"line":4,"column":5}}],'
    '"extensions":{{"code":"INTERNAL_SERVER_ERROR"}}}}]}}}}'
)

invalid_query1_server = [invalid_query1_server_answer]


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [invalid_query1_server], indirect=True)
@pytest.mark.parametrize("query_str", [invalid_query_str])
async def test_websocket_invalid_query(event_loop, client_and_server, query_str):

    session, server = client_and_server

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
@pytest.mark.parametrize("server", [server_invalid_subscription], indirect=True)
@pytest.mark.parametrize("query_str", [invalid_subscription_str])
async def test_websocket_invalid_subscription(event_loop, client_and_server, query_str):

    session, server = client_and_server

    query = gql(query_str)

    with pytest.raises(TransportQueryError) as exc_info:
        async for result in session.subscribe(query):
            pass

    exception = exc_info.value

    assert isinstance(exception.errors, List)

    error = exception.errors[0]

    assert error["extensions"]["code"] == "INTERNAL_SERVER_ERROR"


connection_error_server_answer = (
    '{"type":"connection_error","id":null,'
    '"payload":{"message":"Unexpected token Q in JSON at position 0"}}'
)


async def server_no_ack(ws, path):
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_no_ack], indirect=True)
@pytest.mark.parametrize("query_str", [invalid_query_str])
async def test_websocket_server_does_not_send_ack(event_loop, server, query_str):
    from gql.transport.websockets import WebsocketsTransport

    url = f"ws://{server.hostname}:{server.port}/graphql"

    sample_transport = WebsocketsTransport(url=url, ack_timeout=1)

    with pytest.raises(asyncio.TimeoutError):
        async with Client(transport=sample_transport):
            pass


async def server_connection_error(ws, path):
    await WebSocketServerHelper.send_connection_ack(ws)
    result = await ws.recv()
    print(f"Server received: {result}")
    await ws.send(connection_error_server_answer)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_connection_error], indirect=True)
@pytest.mark.parametrize("query_str", [invalid_query_str])
async def test_websocket_sending_invalid_data(event_loop, client_and_server, query_str):

    session, server = client_and_server

    invalid_data = "QSDF"
    print(f">>> {invalid_data}")
    await session.transport.websocket.send(invalid_data)

    await asyncio.sleep(2 * MS)


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
@pytest.mark.parametrize("server", [server_invalid_payload], indirect=True)
@pytest.mark.parametrize("query_str", [invalid_query_str])
async def test_websocket_sending_invalid_payload(
    event_loop, client_and_server, query_str
):

    session, server = client_and_server

    # Monkey patching the _send_query method to send an invalid payload

    async def monkey_patch_send_query(
        self, document, variable_values=None, operation_name=None,
    ) -> int:
        query_id = self.next_query_id
        self.next_query_id += 1

        query_str = json.dumps(
            {"id": str(query_id), "type": "start", "payload": "BLAHBLAH"}
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
async def test_websocket_transport_protocol_errors(event_loop, client_and_server):

    session, server = client_and_server

    query = gql("query { hello }")

    with pytest.raises(TransportProtocolError):
        await session.execute(query)


async def server_without_ack(ws, path):
    # Sending something else than an ack
    await WebSocketServerHelper.send_complete(ws, 1)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_without_ack], indirect=True)
async def test_websocket_server_does_not_ack(event_loop, server):
    from gql.transport.websockets import WebsocketsTransport

    url = f"ws://{server.hostname}:{server.port}/graphql"
    print(f"url = {url}")

    sample_transport = WebsocketsTransport(url=url)

    with pytest.raises(TransportProtocolError):
        async with Client(transport=sample_transport):
            pass


async def server_closing_directly(ws, path):
    await ws.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_closing_directly], indirect=True)
async def test_websocket_server_closing_directly(event_loop, server):
    import websockets
    from gql.transport.websockets import WebsocketsTransport

    url = f"ws://{server.hostname}:{server.port}/graphql"
    print(f"url = {url}")

    sample_transport = WebsocketsTransport(url=url)

    with pytest.raises(websockets.exceptions.ConnectionClosed):
        async with Client(transport=sample_transport):
            pass


async def server_closing_after_ack(ws, path):
    await WebSocketServerHelper.send_connection_ack(ws)
    await ws.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_closing_after_ack], indirect=True)
async def test_websocket_server_closing_after_ack(event_loop, client_and_server):

    import websockets

    session, server = client_and_server

    query = gql("query { hello }")

    with pytest.raises(websockets.exceptions.ConnectionClosed):
        await session.execute(query)

    await session.transport.wait_closed()

    with pytest.raises(TransportClosed):
        await session.execute(query)


async def server_sending_invalid_query_errors(ws, path):
    await WebSocketServerHelper.send_connection_ack(ws)
    invalid_error = (
        '{"type":"error","id":"404","payload":'
        '{"message":"error for no good reason on non existing query"}}'
    )
    await ws.send(invalid_error)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_sending_invalid_query_errors], indirect=True)
async def test_websocket_server_sending_invalid_query_errors(event_loop, server):
    from gql.transport.websockets import WebsocketsTransport

    url = f"ws://{server.hostname}:{server.port}/graphql"
    print(f"url = {url}")

    sample_transport = WebsocketsTransport(url=url)

    # Invalid server message is ignored
    async with Client(transport=sample_transport):
        await asyncio.sleep(2 * MS)


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_sending_invalid_query_errors], indirect=True)
async def test_websocket_non_regression_bug_105(event_loop, server):
    from gql.transport.websockets import WebsocketsTransport

    # This test will check a fix to a race condition which happens if the user is trying
    # to connect using the same client twice at the same time
    # See bug #105

    url = f"ws://{server.hostname}:{server.port}/graphql"
    print(f"url = {url}")

    sample_transport = WebsocketsTransport(url=url)

    client = Client(transport=sample_transport)

    # Create a coroutine which start the connection with the transport but does nothing
    async def client_connect(client):
        async with client:
            await asyncio.sleep(2 * MS)

    # Create two tasks which will try to connect using the same client (not allowed)
    connect_task1 = asyncio.ensure_future(client_connect(client))
    connect_task2 = asyncio.ensure_future(client_connect(client))

    with pytest.raises(TransportAlreadyConnected):
        await asyncio.gather(connect_task1, connect_task2)


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [invalid_query1_server], indirect=True)
async def test_websocket_using_cli_invalid_query(
    event_loop, server, monkeypatch, capsys
):

    url = f"ws://{server.hostname}:{server.port}/graphql"
    print(f"url = {url}")

    from gql.cli import main, get_parser
    import io

    parser = get_parser(with_examples=True)
    args = parser.parse_args([url])

    # Monkeypatching sys.stdin to simulate getting the query
    # via the standard input
    monkeypatch.setattr("sys.stdin", io.StringIO(invalid_query_str))

    # Flush captured output
    captured = capsys.readouterr()

    await main(args)

    # Check that the error has been printed on stdout
    captured = capsys.readouterr()
    captured_err = str(captured.err).strip()
    print(f"Captured: {captured_err}")

    expected_error = 'Cannot query field "bloh" on type "Continent"'

    assert expected_error in captured_err
