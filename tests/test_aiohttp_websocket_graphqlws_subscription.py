import asyncio
import json
import sys
import warnings
from typing import List

import pytest
from parse import search

from gql import Client, gql
from gql.client import AsyncClientSession
from gql.transport.exceptions import TransportConnectionFailed, TransportServerError

from .conftest import MS, WebSocketServerHelper

# Marking all tests in this file with the aiohttp AND websockets marker
pytestmark = [pytest.mark.aiohttp, pytest.mark.websockets]

countdown_server_answer = (
    '{{"type":"next","id":"{query_id}","payload":{{"data":{{"number":{number}}}}}}}'
)

COUNTING_DELAY = 20 * MS
PING_SENDING_DELAY = 50 * MS
PONG_TIMEOUT = 100 * MS

# List which can used to store received messages by the server
logged_messages: List[str] = []


def server_countdown_factory(
    keepalive=False, answer_pings=True, simulate_disconnect=False
):
    async def server_countdown_template(ws):
        import websockets

        logged_messages.clear()

        try:
            await WebSocketServerHelper.send_connection_ack(
                ws, payload="dummy_connection_ack_payload"
            )

            result = await ws.recv()
            logged_messages.append(result)

            json_result = json.loads(result)
            assert json_result["type"] == "subscribe"
            payload = json_result["payload"]
            query = payload["query"]
            query_id = json_result["id"]

            count_found = search("count: {:d}", query)
            count = count_found[0]
            print(f"            Server: Countdown started from: {count}")

            if simulate_disconnect and count == 8:
                await ws.close()

            pong_received: asyncio.Event = asyncio.Event()

            async def counting_coro():
                print("            Server: counting task started")
                try:
                    for number in range(count, -1, -1):
                        await ws.send(
                            countdown_server_answer.format(
                                query_id=query_id, number=number
                            )
                        )
                        await asyncio.sleep(COUNTING_DELAY)
                finally:
                    print("            Server: counting task ended")

            print("            Server: starting counting task")
            counting_task = asyncio.ensure_future(counting_coro())

            async def keepalive_coro():
                print("            Server: keepalive task started")
                try:
                    while True:
                        await asyncio.sleep(PING_SENDING_DELAY)
                        try:
                            # Send a ping
                            await WebSocketServerHelper.send_ping(
                                ws, payload="dummy_ping_payload"
                            )

                            # Wait for a pong
                            try:
                                await asyncio.wait_for(
                                    pong_received.wait(), PONG_TIMEOUT
                                )
                            except asyncio.TimeoutError:
                                print(
                                    "\n            Server: No pong received in time!\n"
                                )
                                break

                            pong_received.clear()

                        except websockets.exceptions.ConnectionClosed:
                            break
                finally:
                    print("            Server: keepalive task ended")

            if keepalive:
                print("            Server: starting keepalive task")
                keepalive_task = asyncio.ensure_future(keepalive_coro())

            async def receiving_coro():
                print("            Server: receiving task started")
                try:
                    nonlocal counting_task
                    while True:

                        try:
                            result = await ws.recv()
                            logged_messages.append(result)
                        except websockets.exceptions.ConnectionClosed:
                            break

                        json_result = json.loads(result)

                        answer_type = json_result["type"]

                        if answer_type == "complete" and json_result["id"] == str(
                            query_id
                        ):
                            print("Cancelling counting task now")
                            counting_task.cancel()
                            if keepalive:
                                print("Cancelling keep alive task now")
                                keepalive_task.cancel()

                        elif answer_type == "ping":
                            if answer_pings:
                                payload = json_result.get("payload", None)
                                await WebSocketServerHelper.send_pong(
                                    ws, payload=payload
                                )

                        elif answer_type == "pong":
                            pong_received.set()
                finally:
                    print("            Server: receiving task ended")
                    if keepalive:
                        keepalive_task.cancel()

            print("            Server: starting receiving task")
            receiving_task = asyncio.ensure_future(receiving_coro())

            try:
                print("            Server: waiting for counting task to complete")
                await counting_task
            except asyncio.CancelledError:
                print("            Server: Now counting task is cancelled")

            print("            Server: sending complete message")
            await WebSocketServerHelper.send_complete(ws, query_id)

            if keepalive:
                print("            Server: cancelling keepalive task")
                keepalive_task.cancel()
                try:
                    await keepalive_task
                except asyncio.CancelledError:
                    print("            Server: Now keepalive task is cancelled")

            print("            Server: waiting for client to close the connection")
            try:
                await asyncio.wait_for(receiving_task, 1000 * MS)
            except asyncio.TimeoutError:
                pass

            print("            Server: cancelling receiving task")
            receiving_task.cancel()

            try:
                await receiving_task
            except asyncio.CancelledError:
                print("            Server: Now receiving task is cancelled")

        except websockets.exceptions.ConnectionClosedOK:
            pass
        except AssertionError as e:
            print(f"\n            Server: Assertion failed: {e!s}\n")
        finally:
            print("            Server: waiting for websocket connection to close")
            await ws.wait_closed()
            print("            Server: connection closed")

    return server_countdown_template


async def server_countdown(ws):

    server = server_countdown_factory()
    await server(ws)


async def server_countdown_keepalive(ws):

    server = server_countdown_factory(keepalive=True)
    await server(ws)


async def server_countdown_dont_answer_pings(ws):

    server = server_countdown_factory(answer_pings=False)
    await server(ws)


async def server_countdown_disconnect(ws):

    server = server_countdown_factory(simulate_disconnect=True)
    await server(ws)


countdown_subscription_str = """
    subscription {{
      countdown (count: {count}) {{
        number
      }}
    }}
"""


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_graphqlws_subscription(
    client_and_aiohttp_websocket_graphql_server, subscription_str
):

    session, server = client_and_aiohttp_websocket_graphql_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async for result in session.subscribe(subscription):

        number = result["number"]
        print(f"Number received: {number}")

        assert number == count
        count -= 1

    assert count == -1


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_graphqlws_subscription_break(
    client_and_aiohttp_websocket_graphql_server, subscription_str
):

    session, server = client_and_aiohttp_websocket_graphql_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    generator = session.subscribe(subscription)
    async for result in generator:

        number = result["number"]
        print(f"Number received: {number}")

        assert number == count

        if count <= 5:
            break

        count -= 1

    assert count == 5

    # Using aclose here to make it stop cleanly on pypy
    await generator.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_graphqlws_subscription_task_cancel(
    client_and_aiohttp_websocket_graphql_server, subscription_str
):

    session, server = client_and_aiohttp_websocket_graphql_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    task_cancelled = False

    async def task_coro():
        nonlocal count
        nonlocal task_cancelled

        try:
            async for result in session.subscribe(subscription):

                number = result["number"]
                print(f"Number received: {number}")

                assert number == count

                count -= 1
        except asyncio.CancelledError:
            print("Inside task cancelled")
            task_cancelled = True

    task = asyncio.ensure_future(task_coro())

    async def cancel_task_coro():
        nonlocal task

        await asyncio.sleep(5.5 * COUNTING_DELAY)

        task.cancel()

    cancel_task = asyncio.ensure_future(cancel_task_coro())

    await asyncio.gather(task, cancel_task)

    assert count > 0
    assert task_cancelled is True


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_graphqlws_subscription_close_transport(
    client_and_aiohttp_websocket_graphql_server, subscription_str
):

    session, server = client_and_aiohttp_websocket_graphql_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async def task_coro():
        nonlocal count
        async for result in session.subscribe(subscription):

            number = result["number"]
            print(f"Number received: {number}")

            assert number == count

            count -= 1

    task = asyncio.ensure_future(task_coro())

    async def close_transport_task_coro():
        nonlocal task

        await asyncio.sleep(5.5 * COUNTING_DELAY)

        await session.transport.close()

    close_transport_task = asyncio.ensure_future(close_transport_task_coro())

    await asyncio.gather(task, close_transport_task)

    assert count > 0


async def server_countdown_close_connection_in_middle(ws):
    await WebSocketServerHelper.send_connection_ack(ws)

    result = await ws.recv()
    json_result = json.loads(result)
    assert json_result["type"] == "subscribe"
    payload = json_result["payload"]
    query = payload["query"]
    query_id = json_result["id"]

    count_found = search("count: {:d}", query)
    count = count_found[0]
    stopping_before = count // 2
    print(f"Countdown started from: {count}, stopping server before {stopping_before}")
    for number in range(count, stopping_before, -1):
        await ws.send(countdown_server_answer.format(query_id=query_id, number=number))
        await asyncio.sleep(COUNTING_DELAY)

    print("Closing server while subscription is still running now")
    await ws.close()
    await ws.wait_closed()
    print("Server is now closed")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "graphqlws_server", [server_countdown_close_connection_in_middle], indirect=True
)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_graphqlws_subscription_server_connection_closed(
    client_and_aiohttp_websocket_graphql_server, subscription_str
):
    session, _ = client_and_aiohttp_websocket_graphql_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    with pytest.raises(TransportConnectionFailed):
        async for result in session.subscribe(subscription):
            number = result["number"]
            print(f"Number received: {number}")

            assert number == count

            count -= 1


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_graphqlws_subscription_with_operation_name(
    client_and_aiohttp_websocket_graphql_server, subscription_str
):

    session, server = client_and_aiohttp_websocket_graphql_server

    count = 10
    subscription = gql(subscription_str.format(count=count))
    subscription.operation_name = "CountdownSubscription"

    async for result in session.subscribe(subscription):

        number = result["number"]
        print(f"Number received: {number}")

        assert number == count
        count -= 1

    assert count == -1

    # Check that the query contains the operationName
    assert '"operationName": "CountdownSubscription"' in logged_messages[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "graphqlws_server", [server_countdown_keepalive], indirect=True
)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_graphqlws_subscription_with_keepalive(
    client_and_aiohttp_websocket_graphql_server, subscription_str
):

    session, server = client_and_aiohttp_websocket_graphql_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async for result in session.subscribe(subscription):

        number = result["number"]
        print(f"Number received: {number}")

        assert number == count
        count -= 1

    assert count == -1
    assert "ping" in session.transport.payloads
    assert session.transport.payloads["ping"] == "dummy_ping_payload"
    assert (
        session.transport.payloads["connection_ack"] == "dummy_connection_ack_payload"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "graphqlws_server", [server_countdown_keepalive], indirect=True
)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_graphqlws_subscription_with_keepalive_with_timeout_ok(
    graphqlws_server, subscription_str
):

    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    path = "/graphql"
    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}{path}"
    transport = AIOHTTPWebsocketsTransport(
        url=url, keep_alive_timeout=(5 * COUNTING_DELAY)
    )

    client = Client(transport=transport)

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async with client as session:
        async for result in session.subscribe(subscription):

            number = result["number"]
            print(f"Number received: {number}")

            assert number == count
            count -= 1

    assert count == -1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "graphqlws_server", [server_countdown_keepalive], indirect=True
)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_graphqlws_subscription_with_keepalive_with_timeout_nok(
    graphqlws_server, subscription_str
):

    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    path = "/graphql"
    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}{path}"
    transport = AIOHTTPWebsocketsTransport(
        url=url, keep_alive_timeout=(COUNTING_DELAY / 2)
    )

    client = Client(transport=transport)

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async with client as session:
        with pytest.raises(TransportServerError) as exc_info:
            async for result in session.subscribe(subscription):

                number = result["number"]
                print(f"Number received: {number}")

                assert number == count
                count -= 1

        assert "No keep-alive message has been received" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "graphqlws_server", [server_countdown_keepalive], indirect=True
)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_graphqlws_subscription_with_ping_interval_ok(
    graphqlws_server, subscription_str
):

    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    path = "/graphql"
    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}{path}"
    transport = AIOHTTPWebsocketsTransport(
        url=url,
        ping_interval=(10 * COUNTING_DELAY),
        pong_timeout=(8 * COUNTING_DELAY),
    )

    client = Client(transport=transport)

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async with client as session:
        async for result in session.subscribe(subscription):

            number = result["number"]
            print(f"Number received: {number}")

            assert number == count
            count -= 1

    assert count == -1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "graphqlws_server", [server_countdown_dont_answer_pings], indirect=True
)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_graphqlws_subscription_with_ping_interval_nok(
    graphqlws_server, subscription_str
):

    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    path = "/graphql"
    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}{path}"
    transport = AIOHTTPWebsocketsTransport(url=url, ping_interval=(5 * COUNTING_DELAY))

    client = Client(transport=transport)

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async with client as session:
        with pytest.raises(TransportServerError) as exc_info:
            async for result in session.subscribe(subscription):

                number = result["number"]
                print(f"Number received: {number}")

                assert number == count
                count -= 1

        assert "No pong received" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "graphqlws_server", [server_countdown_keepalive], indirect=True
)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_graphqlws_subscription_manual_pings_with_payload(
    graphqlws_server, subscription_str
):

    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    path = "/graphql"
    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}{path}"
    transport = AIOHTTPWebsocketsTransport(url=url)

    client = Client(transport=transport)

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async with client as session:
        async for result in session.subscribe(subscription):

            number = result["number"]
            print(f"Number received: {number}")

            payload = {"count_received": count}

            await transport.send_ping(payload=payload)

            await asyncio.wait_for(transport.pong_received.wait(), 10000 * MS)

            transport.pong_received.clear()

            assert transport.payloads["pong"] == payload

            assert number == count
            count -= 1

    assert count == -1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "graphqlws_server", [server_countdown_keepalive], indirect=True
)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_graphqlws_subscription_manual_pong_with_payload(
    graphqlws_server, subscription_str
):

    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    path = "/graphql"
    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}{path}"
    transport = AIOHTTPWebsocketsTransport(url=url, answer_pings=False)

    client = Client(transport=transport)

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async with client as session:

        async def answer_ping_coro():
            while True:
                await transport.ping_received.wait()
                transport.ping_received.clear()
                await transport.send_pong(payload={"some": "data"})

        answer_ping_task = asyncio.ensure_future(answer_ping_coro())

        try:
            async for result in session.subscribe(subscription):

                number = result["number"]
                print(f"Number received: {number}")

                assert number == count
                count -= 1

        finally:
            answer_ping_task.cancel()

    assert count == -1


@pytest.mark.parametrize(
    "graphqlws_server", [server_countdown_keepalive], indirect=True
)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
def test_aiohttp_websocket_graphqlws_subscription_sync(
    graphqlws_server, subscription_str
):
    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}/graphql"
    print(f"url = {url}")

    transport = AIOHTTPWebsocketsTransport(url=url)

    client = Client(transport=transport)

    count = 10
    subscription = gql(subscription_str.format(count=count))

    for result in client.subscribe(subscription):

        number = result["number"]
        print(f"Number received: {number}")

        assert number == count
        count -= 1

    assert count == -1


@pytest.mark.skipif(sys.platform.startswith("win"), reason="test failing on windows")
@pytest.mark.parametrize(
    "graphqlws_server", [server_countdown_keepalive], indirect=True
)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
def test_aiohttp_websocket_graphqlws_subscription_sync_graceful_shutdown(
    graphqlws_server, subscription_str
):
    """Note: this test will simulate a control-C happening while a sync subscription
    is in progress. To do that we will throw a KeyboardInterrupt exception inside
    the subscription async generator.

    The code should then do a clean close:
      - send stop messages for each active query
      - send a connection_terminate message
    Then the KeyboardInterrupt will be reraise (to warn potential user code)

    This test does not work on Windows but the behaviour with Windows is correct.
    """
    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}/graphql"
    print(f"url = {url}")

    transport = AIOHTTPWebsocketsTransport(url=url)

    client = Client(transport=transport)

    count = 10
    subscription = gql(subscription_str.format(count=count))

    with pytest.raises(KeyboardInterrupt):
        for result in client.subscribe(subscription):

            number = result["number"]
            print(f"Number received: {number}")

            assert number == count

            if count == 5:

                # Simulate a KeyboardInterrupt in the generator
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore", message="There is no current event loop"
                    )
                    assert isinstance(client.session, AsyncClientSession)
                    asyncio.ensure_future(
                        client.session._generator.athrow(KeyboardInterrupt)
                    )

            count -= 1

    assert count == 4

    # Check that the server received a connection_terminate message last
    # assert logged_messages.pop() == '{"type": "connection_terminate"}'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "graphqlws_server", [server_countdown_keepalive], indirect=True
)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_graphqlws_subscription_running_in_thread(
    graphqlws_server, subscription_str, run_sync_test
):
    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    def test_code():
        path = "/graphql"
        url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}{path}"
        transport = AIOHTTPWebsocketsTransport(url=url)

        client = Client(transport=transport)

        count = 10
        subscription = gql(subscription_str.format(count=count))

        for result in client.subscribe(subscription):

            number = result["number"]
            print(f"Number received: {number}")

            assert number == count
            count -= 1

        assert count == -1

    await run_sync_test(graphqlws_server, test_code)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "graphqlws_server", [server_countdown_disconnect], indirect=True
)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
@pytest.mark.parametrize("execute_instead_of_subscribe", [False, True])
async def test_aiohttp_websocket_graphqlws_subscription_reconnecting_session(
    graphqlws_server, subscription_str, execute_instead_of_subscribe
):

    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    path = "/graphql"
    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}{path}"
    transport = AIOHTTPWebsocketsTransport(url=url)

    client = Client(transport=transport)

    count = 8
    subscription_with_disconnect = gql(subscription_str.format(count=count))

    count = 10
    subscription = gql(subscription_str.format(count=count))

    session = await client.connect_async(
        reconnecting=True, retry_connect=False, retry_execute=False
    )

    # First we make a query or subscription which will cause a disconnect
    # in the backend (count=8)
    try:
        if execute_instead_of_subscribe:
            print("\nEXECUTION_1\n")
            await session.execute(subscription_with_disconnect)
        else:
            print("\nSUBSCRIPTION_1_WITH_DISCONNECT\n")
            async for result in session.subscribe(subscription_with_disconnect):
                pass
    except TransportConnectionFailed:
        pass

    # Wait for disconnect
    for i in range(200):
        await asyncio.sleep(1 * MS)
        if not transport._connected:
            print(f"\nDisconnected in {i+1} MS")
            break

    # Wait for reconnect
    for i in range(200):
        await asyncio.sleep(1 * MS)
        if transport._connected:
            print(f"\nConnected again in {i+1} MS")
            break

    assert transport._connected is True

    # Then after the reconnection, we make a query or a subscription
    if execute_instead_of_subscribe:
        print("\nEXECUTION_2\n")
        result = await session.execute(subscription)
        assert result["number"] == 10
    else:
        print("\nSUBSCRIPTION_2\n")
        generator = session.subscribe(subscription)
        async for result in generator:
            number = result["number"]
            print(f"Number received: {number}")

            assert number == count
            count -= 1

        await generator.aclose()

        assert count == -1

    # Close the reconnecting session
    await client.close_async()

    # Wait for disconnect
    for i in range(200):
        await asyncio.sleep(1 * MS)
        if not transport._connected:
            print(f"\nDisconnected in {i+1} MS")
            break

    assert transport._connected is False
