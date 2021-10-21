import asyncio
import json
import sys
from typing import List

import pytest
from parse import search

from gql import Client, gql
from gql.transport.exceptions import TransportServerError

from .conftest import MS, WebSocketServerHelper

# Marking all tests in this file with the websockets marker
pytestmark = pytest.mark.websockets

countdown_server_answer = (
    '{{"type":"next","id":"{query_id}","payload":{{"data":{{"number":{number}}}}}}}'
)

WITH_KEEPALIVE = False

COUNTING_DELAY = 2 * MS
PING_SENDING_DELAY = 5 * MS
PONG_TIMEOUT = 2 * MS

# List which can used to store received messages by the server
logged_messages: List[str] = []


async def server_countdown(ws, path):
    import websockets

    logged_messages.clear()

    global WITH_KEEPALIVE
    try:
        await WebSocketServerHelper.send_connection_ack(ws)

        result = await ws.recv()
        logged_messages.append(result)

        json_result = json.loads(result)
        assert json_result["type"] == "subscribe"
        payload = json_result["payload"]
        query = payload["query"]
        query_id = json_result["id"]

        count_found = search("count: {:d}", query)
        count = count_found[0]
        print(f"Countdown started from: {count}")

        pong_received: asyncio.Event = asyncio.Event()

        async def counting_coro():
            for number in range(count, -1, -1):
                await ws.send(
                    countdown_server_answer.format(query_id=query_id, number=number)
                )
                await asyncio.sleep(COUNTING_DELAY)

        counting_task = asyncio.ensure_future(counting_coro())

        async def keepalive_coro():
            while True:
                await asyncio.sleep(PING_SENDING_DELAY)
                try:
                    # Send a ping
                    await WebSocketServerHelper.send_ping(ws)

                    # Wait for a pong
                    try:
                        await asyncio.wait_for(pong_received.wait(), PONG_TIMEOUT)
                    except asyncio.TimeoutError:
                        print("\nNo pong received in time!\n")

                    pong_received.clear()

                except websockets.exceptions.ConnectionClosed:
                    break

        if WITH_KEEPALIVE:
            keepalive_task = asyncio.ensure_future(keepalive_coro())

        async def stopping_coro():
            nonlocal counting_task
            while True:

                try:
                    result = await ws.recv()
                    logged_messages.append(result)
                except websockets.exceptions.ConnectionClosed:
                    break

                json_result = json.loads(result)

                answer_type = json_result["type"]
                if answer_type == "complete" and json_result["id"] == str(query_id):
                    print("Cancelling counting task now")
                    counting_task.cancel()
                    if WITH_KEEPALIVE:
                        print("Cancelling keep alive task now")
                        keepalive_task.cancel()
                elif answer_type == "pong":
                    pong_received.set()

        stopping_task = asyncio.ensure_future(stopping_coro())

        try:
            await counting_task
        except asyncio.CancelledError:
            print("Now counting task is cancelled")

        stopping_task.cancel()

        try:
            await stopping_task
        except asyncio.CancelledError:
            print("Now stopping task is cancelled")

        if WITH_KEEPALIVE:
            keepalive_task.cancel()
            try:
                await keepalive_task
            except asyncio.CancelledError:
                print("Now keepalive task is cancelled")

        await WebSocketServerHelper.send_complete(ws, query_id)
    except websockets.exceptions.ConnectionClosedOK:
        pass
    except AssertionError as e:
        print(f"\nAssertion failed: {e!s}\n")
    finally:
        await ws.wait_closed()


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
async def test_graphqlws_subscription(
    event_loop, client_and_graphqlws_server, subscription_str
):

    session, server = client_and_graphqlws_server

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
async def test_graphqlws_subscription_break(
    event_loop, client_and_graphqlws_server, subscription_str
):

    session, server = client_and_graphqlws_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async for result in session.subscribe(subscription):

        number = result["number"]
        print(f"Number received: {number}")

        assert number == count

        if count <= 5:
            # Note: the following line is only necessary for pypy3 v3.6.1
            if sys.version_info < (3, 7):
                await session._generator.aclose()
            break

        count -= 1

    assert count == 5


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_graphqlws_subscription_task_cancel(
    event_loop, client_and_graphqlws_server, subscription_str
):

    session, server = client_and_graphqlws_server

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

    async def cancel_task_coro():
        nonlocal task

        await asyncio.sleep(5.5 * COUNTING_DELAY)

        task.cancel()

    cancel_task = asyncio.ensure_future(cancel_task_coro())

    await asyncio.gather(task, cancel_task)

    assert count > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_graphqlws_subscription_close_transport(
    event_loop, client_and_graphqlws_server, subscription_str
):

    session, server = client_and_graphqlws_server

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


async def server_countdown_close_connection_in_middle(ws, path):
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
async def test_graphqlws_subscription_server_connection_closed(
    event_loop, client_and_graphqlws_server, subscription_str
):
    import websockets

    session, server = client_and_graphqlws_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    with pytest.raises(websockets.exceptions.ConnectionClosedOK):

        async for result in session.subscribe(subscription):

            number = result["number"]
            print(f"Number received: {number}")

            assert number == count

            count -= 1


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_graphqlws_subscription_with_operation_name(
    event_loop, client_and_graphqlws_server, subscription_str
):

    session, server = client_and_graphqlws_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async for result in session.subscribe(
        subscription, operation_name="CountdownSubscription"
    ):

        number = result["number"]
        print(f"Number received: {number}")

        assert number == count
        count -= 1

    assert count == -1

    # Check that the query contains the operationName
    assert '"operationName": "CountdownSubscription"' in logged_messages[0]


WITH_KEEPALIVE = True


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_graphqlws_subscription_with_keepalive(
    event_loop, client_and_graphqlws_server, subscription_str
):

    session, server = client_and_graphqlws_server

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
async def test_graphqlws_subscription_with_keepalive_with_timeout_ok(
    event_loop, graphqlws_server, subscription_str
):

    from gql.transport.websockets import WebsocketsTransport

    path = "/graphql"
    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}{path}"
    sample_transport = WebsocketsTransport(
        url=url, keep_alive_timeout=(5 * COUNTING_DELAY)
    )

    client = Client(transport=sample_transport)

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
@pytest.mark.parametrize("graphqlws_server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_graphqlws_subscription_with_keepalive_with_timeout_nok(
    event_loop, graphqlws_server, subscription_str
):

    from gql.transport.websockets import WebsocketsTransport

    path = "/graphql"
    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}{path}"
    sample_transport = WebsocketsTransport(
        url=url, keep_alive_timeout=(COUNTING_DELAY / 2)
    )

    client = Client(transport=sample_transport)

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


@pytest.mark.parametrize("graphqlws_server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
def test_graphqlws_subscription_sync(graphqlws_server, subscription_str):
    from gql.transport.websockets import WebsocketsTransport

    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}/graphql"
    print(f"url = {url}")

    sample_transport = WebsocketsTransport(url=url)

    client = Client(transport=sample_transport)

    count = 10
    subscription = gql(subscription_str.format(count=count))

    for result in client.subscribe(subscription):

        number = result["number"]
        print(f"Number received: {number}")

        assert number == count
        count -= 1

    assert count == -1


@pytest.mark.skipif(sys.platform.startswith("win"), reason="test failing on windows")
@pytest.mark.parametrize("graphqlws_server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
def test_graphqlws_subscription_sync_graceful_shutdown(
    graphqlws_server, subscription_str
):
    """ Note: this test will simulate a control-C happening while a sync subscription
    is in progress. To do that we will throw a KeyboardInterrupt exception inside
    the subscription async generator.

    The code should then do a clean close:
      - send stop messages for each active query
      - send a connection_terminate message
    Then the KeyboardInterrupt will be reraise (to warn potential user code)

    This test does not work on Windows but the behaviour with Windows is correct.
    """
    from gql.transport.websockets import WebsocketsTransport

    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}/graphql"
    print(f"url = {url}")

    sample_transport = WebsocketsTransport(url=url)

    client = Client(transport=sample_transport)

    count = 10
    subscription = gql(subscription_str.format(count=count))

    with pytest.raises(KeyboardInterrupt):
        for result in client.subscribe(subscription):

            number = result["number"]
            print(f"Number received: {number}")

            assert number == count

            if count == 5:

                # Simulate a KeyboardInterrupt in the generator
                asyncio.ensure_future(
                    client.session._generator.athrow(KeyboardInterrupt)
                )

            count -= 1

    assert count == 4

    # Check that the server received a connection_terminate message last
    # assert logged_messages.pop() == '{"type": "connection_terminate"}'


@pytest.mark.asyncio
@pytest.mark.parametrize("graphqlws_server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_graphqlws_subscription_running_in_thread(
    event_loop, graphqlws_server, subscription_str, run_sync_test
):
    from gql.transport.websockets import WebsocketsTransport

    def test_code():
        path = "/graphql"
        url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}{path}"
        sample_transport = WebsocketsTransport(url=url)

        client = Client(transport=sample_transport)

        count = 10
        subscription = gql(subscription_str.format(count=count))

        for result in client.subscribe(subscription):

            number = result["number"]
            print(f"Number received: {number}")

            assert number == count
            count -= 1

        assert count == -1

    await run_sync_test(event_loop, graphqlws_server, test_code)
