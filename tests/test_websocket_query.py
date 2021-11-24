import asyncio
import json
import ssl
import sys
from typing import Dict

import pytest

from gql import Client, gql
from gql.transport.exceptions import (
    TransportAlreadyConnected,
    TransportClosed,
    TransportQueryError,
    TransportServerError,
)

from .conftest import MS, WebSocketServerHelper

# Marking all tests in this file with the websockets marker
pytestmark = pytest.mark.websockets

query1_str = """
    query getContinents {
      continents {
        code
        name
      }
    }
"""

query1_server_answer_data = (
    '{"continents":['
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
    '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
    '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
    '{"code":"SA","name":"South America"}]}'
)

query1_server_answer = (
    '{{"type":"data","id":"{query_id}","payload":{{"data":{{"continents":['
    '{{"code":"AF","name":"Africa"}},{{"code":"AN","name":"Antarctica"}},'
    '{{"code":"AS","name":"Asia"}},{{"code":"EU","name":"Europe"}},'
    '{{"code":"NA","name":"North America"}},{{"code":"OC","name":"Oceania"}},'
    '{{"code":"SA","name":"South America"}}]}}}}}}'
)

server1_answers = [
    query1_server_answer,
]


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server1_answers], indirect=True)
async def test_websocket_starting_client_in_context_manager(event_loop, server):
    import websockets
    from gql.transport.websockets import WebsocketsTransport

    url = f"ws://{server.hostname}:{server.port}/graphql"
    print(f"url = {url}")

    sample_transport = WebsocketsTransport(url=url)

    async with Client(transport=sample_transport) as session:

        assert isinstance(
            sample_transport.websocket, websockets.client.WebSocketClientProtocol
        )

        query1 = gql(query1_str)

        result = await session.execute(query1)

        print("Client received:", result)

        # Verify result
        assert isinstance(result, Dict)

        continents = result["continents"]
        africa = continents[0]

        assert africa["code"] == "AF"

    # Check client is disconnect here
    assert sample_transport.websocket is None


@pytest.mark.asyncio
@pytest.mark.parametrize("ws_ssl_server", [server1_answers], indirect=True)
async def test_websocket_using_ssl_connection(event_loop, ws_ssl_server):
    import websockets
    from gql.transport.websockets import WebsocketsTransport

    server = ws_ssl_server

    url = f"wss://{server.hostname}:{server.port}/graphql"
    print(f"url = {url}")

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.load_verify_locations(ws_ssl_server.testcert)

    sample_transport = WebsocketsTransport(url=url, ssl=ssl_context)

    async with Client(transport=sample_transport) as session:

        assert isinstance(
            sample_transport.websocket, websockets.client.WebSocketClientProtocol
        )

        query1 = gql(query1_str)

        result = await session.execute(query1)

        print("Client received:", result)

        # Verify result
        assert isinstance(result, Dict)

        continents = result["continents"]
        africa = continents[0]

        assert africa["code"] == "AF"

    # Check client is disconnect here
    assert sample_transport.websocket is None


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server1_answers], indirect=True)
@pytest.mark.parametrize("query_str", [query1_str])
async def test_websocket_simple_query(event_loop, client_and_server, query_str):

    session, server = client_and_server

    query = gql(query_str)

    result = await session.execute(query)

    print("Client received:", result)


server1_two_answers_in_series = [
    query1_server_answer,
    query1_server_answer,
]


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server1_two_answers_in_series], indirect=True)
@pytest.mark.parametrize("query_str", [query1_str])
async def test_websocket_two_queries_in_series(
    event_loop, client_and_server, query_str
):

    session, server = client_and_server

    query = gql(query_str)

    result1 = await session.execute(query)

    print("Query1 received:", result1)

    result2 = await session.execute(query)

    print("Query2 received:", result2)

    assert result1 == result2


async def server1_two_queries_in_parallel(ws, path):
    await WebSocketServerHelper.send_connection_ack(ws)
    result = await ws.recv()
    print(f"Server received: {result}", file=sys.stderr)
    result = await ws.recv()
    print(f"Server received: {result}", file=sys.stderr)
    await ws.send(query1_server_answer.format(query_id=1))
    await ws.send(query1_server_answer.format(query_id=2))
    await WebSocketServerHelper.send_complete(ws, 1)
    await WebSocketServerHelper.send_complete(ws, 2)
    await WebSocketServerHelper.wait_connection_terminate(ws)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server1_two_queries_in_parallel], indirect=True)
@pytest.mark.parametrize("query_str", [query1_str])
async def test_websocket_two_queries_in_parallel(
    event_loop, client_and_server, query_str
):

    session, server = client_and_server

    query = gql(query_str)

    result1 = None
    result2 = None

    async def task1_coro():
        nonlocal result1
        result1 = await session.execute(query)

    async def task2_coro():
        nonlocal result2
        result2 = await session.execute(query)

    task1 = asyncio.ensure_future(task1_coro())
    task2 = asyncio.ensure_future(task2_coro())

    await asyncio.gather(task1, task2)

    print("Query1 received:", result1)
    print("Query2 received:", result2)

    assert result1 == result2


async def server_closing_while_we_are_doing_something_else(ws, path):
    await WebSocketServerHelper.send_connection_ack(ws)
    result = await ws.recv()
    print(f"Server received: {result}", file=sys.stderr)
    await ws.send(query1_server_answer.format(query_id=1))
    await WebSocketServerHelper.send_complete(ws, 1)
    await asyncio.sleep(1 * MS)

    # Closing server after first query
    await ws.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "server", [server_closing_while_we_are_doing_something_else], indirect=True
)
@pytest.mark.parametrize("query_str", [query1_str])
async def test_websocket_server_closing_after_first_query(
    event_loop, client_and_server, query_str
):

    session, server = client_and_server

    query = gql(query_str)

    # First query is working
    await session.execute(query)

    # Then we do other things
    await asyncio.sleep(100 * MS)

    # Now the server is closed but we don't know it yet, we have to send a query
    # to notice it and to receive the exception
    with pytest.raises(TransportClosed):
        await session.execute(query)


ignore_invalid_id_answers = [
    query1_server_answer,
    '{"type":"complete","id": "55"}',
    query1_server_answer,
]


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [ignore_invalid_id_answers], indirect=True)
@pytest.mark.parametrize("query_str", [query1_str])
async def test_websocket_ignore_invalid_id(event_loop, client_and_server, query_str):

    session, server = client_and_server

    query = gql(query_str)

    # First query is working
    await session.execute(query)

    # Second query gets no answer -> raises
    with pytest.raises(TransportQueryError):
        await session.execute(query)

    # Third query is working
    await session.execute(query)


async def assert_client_is_working(session):
    query1 = gql(query1_str)

    result = await session.execute(query1)

    print("Client received:", result)

    # Verify result
    assert isinstance(result, Dict)

    continents = result["continents"]
    africa = continents[0]

    assert africa["code"] == "AF"


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server1_answers], indirect=True)
async def test_websocket_multiple_connections_in_series(event_loop, server):
    from gql.transport.websockets import WebsocketsTransport

    url = f"ws://{server.hostname}:{server.port}/graphql"
    print(f"url = {url}")

    sample_transport = WebsocketsTransport(url=url)

    async with Client(transport=sample_transport) as session:
        await assert_client_is_working(session)

    # Check client is disconnect here
    assert sample_transport.websocket is None

    async with Client(transport=sample_transport) as session:
        await assert_client_is_working(session)

    # Check client is disconnect here
    assert sample_transport.websocket is None


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server1_answers], indirect=True)
async def test_websocket_multiple_connections_in_parallel(event_loop, server):
    from gql.transport.websockets import WebsocketsTransport

    url = f"ws://{server.hostname}:{server.port}/graphql"
    print(f"url = {url}")

    async def task_coro():
        sample_transport = WebsocketsTransport(url=url)
        async with Client(transport=sample_transport) as session:
            await assert_client_is_working(session)

    task1 = asyncio.ensure_future(task_coro())
    task2 = asyncio.ensure_future(task_coro())

    await asyncio.gather(task1, task2)


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server1_answers], indirect=True)
async def test_websocket_trying_to_connect_to_already_connected_transport(
    event_loop, server
):
    from gql.transport.websockets import WebsocketsTransport

    url = f"ws://{server.hostname}:{server.port}/graphql"
    print(f"url = {url}")

    sample_transport = WebsocketsTransport(url=url)
    async with Client(transport=sample_transport) as session:
        await assert_client_is_working(session)

        with pytest.raises(TransportAlreadyConnected):
            async with Client(transport=sample_transport):
                pass


async def server_with_authentication_in_connection_init_payload(ws, path):
    # Wait the connection_init message
    init_message_str = await ws.recv()
    init_message = json.loads(init_message_str)
    payload = init_message["payload"]

    if "Authorization" in payload:
        if payload["Authorization"] == 12345:
            await ws.send('{"type":"connection_ack"}')

            result = await ws.recv()
            print(f"Server received: {result}", file=sys.stderr)
            await ws.send(query1_server_answer.format(query_id=1))
            await WebSocketServerHelper.send_complete(ws, 1)
        else:
            await ws.send(
                '{"type":"connection_error", "payload": "Invalid Authorization token"}'
            )
    else:
        await ws.send(
            '{"type":"connection_error", "payload": "No Authorization token"}'
        )

    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "server", [server_with_authentication_in_connection_init_payload], indirect=True
)
@pytest.mark.parametrize("query_str", [query1_str])
async def test_websocket_connect_success_with_authentication_in_connection_init(
    event_loop, server, query_str
):
    from gql.transport.websockets import WebsocketsTransport

    url = f"ws://{server.hostname}:{server.port}/graphql"
    print(f"url = {url}")

    init_payload = {"Authorization": 12345}

    sample_transport = WebsocketsTransport(url=url, init_payload=init_payload)

    async with Client(transport=sample_transport) as session:

        query1 = gql(query_str)

        result = await session.execute(query1)

        print("Client received:", result)

        # Verify result
        assert isinstance(result, Dict)

        continents = result["continents"]
        africa = continents[0]

        assert africa["code"] == "AF"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "server", [server_with_authentication_in_connection_init_payload], indirect=True
)
@pytest.mark.parametrize("query_str", [query1_str])
@pytest.mark.parametrize("init_payload", [{}, {"Authorization": "invalid_code"}])
async def test_websocket_connect_failed_with_authentication_in_connection_init(
    event_loop, server, query_str, init_payload
):
    from gql.transport.websockets import WebsocketsTransport

    url = f"ws://{server.hostname}:{server.port}/graphql"
    print(f"url = {url}")

    sample_transport = WebsocketsTransport(url=url, init_payload=init_payload)

    with pytest.raises(TransportServerError):
        async with Client(transport=sample_transport) as session:
            query1 = gql(query_str)

            await session.execute(query1)


@pytest.mark.parametrize("server", [server1_answers], indirect=True)
def test_websocket_execute_sync(server):
    from gql.transport.websockets import WebsocketsTransport

    url = f"ws://{server.hostname}:{server.port}/graphql"
    print(f"url = {url}")

    sample_transport = WebsocketsTransport(url=url)

    client = Client(transport=sample_transport)

    query1 = gql(query1_str)

    result = client.execute(query1)

    print("Client received:", result)

    # Verify result
    assert isinstance(result, Dict)

    continents = result["continents"]
    africa = continents[0]

    assert africa["code"] == "AF"

    # Execute sync a second time
    result = client.execute(query1)

    print("Client received:", result)

    # Verify result
    assert isinstance(result, Dict)

    continents = result["continents"]
    africa = continents[0]

    assert africa["code"] == "AF"

    # Check client is disconnect here
    assert sample_transport.websocket is None


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server1_answers], indirect=True)
async def test_websocket_add_extra_parameters_to_connect(event_loop, server):
    from gql.transport.websockets import WebsocketsTransport

    url = f"ws://{server.hostname}:{server.port}/graphql"

    # Increase max payload size to avoid websockets.exceptions.PayloadTooBig exceptions
    sample_transport = WebsocketsTransport(url=url, connect_args={"max_size": 2 ** 21})

    query = gql(query1_str)

    async with Client(transport=sample_transport) as session:
        await session.execute(query)


async def server_sending_keep_alive_before_connection_ack(ws, path):
    await WebSocketServerHelper.send_keepalive(ws)
    await WebSocketServerHelper.send_keepalive(ws)
    await WebSocketServerHelper.send_keepalive(ws)
    await WebSocketServerHelper.send_keepalive(ws)
    await WebSocketServerHelper.send_connection_ack(ws)
    result = await ws.recv()
    print(f"Server received: {result}", file=sys.stderr)
    await ws.send(query1_server_answer.format(query_id=1))
    await WebSocketServerHelper.send_complete(ws, 1)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "server", [server_sending_keep_alive_before_connection_ack], indirect=True
)
@pytest.mark.parametrize("query_str", [query1_str])
async def test_websocket_non_regression_bug_108(
    event_loop, client_and_server, query_str
):

    # This test will check that we now ignore keepalive message
    # arriving before the connection_ack
    # See bug #108

    session, server = client_and_server

    query = gql(query_str)

    result = await session.execute(query)

    print("Client received:", result)

    continents = result["continents"]
    africa = continents[0]

    assert africa["code"] == "AF"


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server1_answers], indirect=True)
async def test_websocket_using_cli(event_loop, server, monkeypatch, capsys):

    url = f"ws://{server.hostname}:{server.port}/graphql"
    print(f"url = {url}")

    from gql.cli import main, get_parser
    import io
    import json

    parser = get_parser(with_examples=True)
    args = parser.parse_args([url])

    # Monkeypatching sys.stdin to simulate getting the query
    # via the standard input
    monkeypatch.setattr("sys.stdin", io.StringIO(query1_str))

    # Flush captured output
    captured = capsys.readouterr()

    exit_code = await main(args)

    assert exit_code == 0

    # Check that the result has been printed on stdout
    captured = capsys.readouterr()
    captured_out = str(captured.out).strip()

    expected_answer = json.loads(query1_server_answer_data)
    print(f"Captured: {captured_out}")
    received_answer = json.loads(captured_out)

    assert received_answer == expected_answer


query1_server_answer_with_extensions = (
    '{{"type":"data","id":"{query_id}","payload":{{"data":{{"continents":['
    '{{"code":"AF","name":"Africa"}},{{"code":"AN","name":"Antarctica"}},'
    '{{"code":"AS","name":"Asia"}},{{"code":"EU","name":"Europe"}},'
    '{{"code":"NA","name":"North America"}},{{"code":"OC","name":"Oceania"}},'
    '{{"code":"SA","name":"South America"}}]}},'
    '"extensions": {{"key1": "val1"}}}}}}'
)

server1_answers_with_extensions = [
    query1_server_answer_with_extensions,
]


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server1_answers_with_extensions], indirect=True)
@pytest.mark.parametrize("query_str", [query1_str])
async def test_websocket_simple_query_with_extensions(
    event_loop, client_and_server, query_str
):

    session, server = client_and_server

    query = gql(query_str)

    execution_result = await session.execute(query, get_execution_result=True)

    assert execution_result.extensions["key1"] == "val1"
