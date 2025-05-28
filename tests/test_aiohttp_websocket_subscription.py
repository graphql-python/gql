import asyncio
import json
import sys
import warnings
from typing import List

import pytest
from graphql import ExecutionResult
from parse import search

from gql import Client, gql
from gql.client import AsyncClientSession
from gql.transport.exceptions import TransportConnectionFailed, TransportServerError

from .conftest import MS, WebSocketServerHelper
from .starwars.schema import StarWarsIntrospection, StarWarsSchema, StarWarsTypeDef

# Marking all tests in this file with the aiohttp AND websockets marker
pytestmark = [pytest.mark.aiohttp, pytest.mark.websockets]

starwars_expected_one = {
    "stars": 3,
    "commentary": "Was expecting more stuff",
    "episode": "JEDI",
}

starwars_expected_two = {
    "stars": 5,
    "commentary": "This is a great movie!",
    "episode": "JEDI",
}


async def server_starwars(ws):
    import websockets

    await WebSocketServerHelper.send_connection_ack(ws)

    try:
        await ws.recv()

        reviews = [starwars_expected_one, starwars_expected_two]

        for review in reviews:

            data = (
                '{"type":"data","id":"1","payload":{"data":{"reviewAdded": '
                + json.dumps(review)
                + "}}}"
            )
            await ws.send(data)
            await asyncio.sleep(2 * MS)

        await WebSocketServerHelper.send_complete(ws, 1)
        await WebSocketServerHelper.wait_connection_terminate(ws)

    except websockets.exceptions.ConnectionClosedOK:
        pass

    print("Server is now closed")


starwars_subscription_str = """
    subscription ListenEpisodeReviews($ep: Episode!) {
      reviewAdded(episode: $ep) {
        stars,
        commentary,
        episode
      }
    }
"""

starwars_invalid_subscription_str = """
    subscription ListenEpisodeReviews($ep: Episode!) {
      reviewAdded(episode: $ep) {
        not_valid_field,
        stars,
        commentary,
        episode
      }
    }
"""

countdown_server_answer = (
    '{{"type":"data","id":"{query_id}","payload":{{"data":{{"number":{number}}}}}}}'
)

WITH_KEEPALIVE = False


# List which can used to store received messages by the server
logged_messages: List[str] = []


async def server_countdown(ws):
    import websockets

    logged_messages.clear()

    global WITH_KEEPALIVE
    try:
        await WebSocketServerHelper.send_connection_ack(ws)
        if WITH_KEEPALIVE:
            await WebSocketServerHelper.send_keepalive(ws)

        result = await ws.recv()
        logged_messages.append(result)

        json_result = json.loads(result)
        assert json_result["type"] == "start"
        payload = json_result["payload"]
        query = payload["query"]
        query_id = json_result["id"]

        count_found = search("count: {:d}", query)
        count = count_found[0]
        print(f"Countdown started from: {count}")

        async def counting_coro():
            for number in range(count, -1, -1):
                await ws.send(
                    countdown_server_answer.format(query_id=query_id, number=number)
                )
                await asyncio.sleep(2 * MS)

        counting_task = asyncio.ensure_future(counting_coro())

        async def stopping_coro():
            nonlocal counting_task
            while True:

                try:
                    result = await ws.recv()
                    logged_messages.append(result)
                except websockets.exceptions.ConnectionClosed:
                    break

                json_result = json.loads(result)

                if json_result["type"] == "stop" and json_result["id"] == str(query_id):
                    print("Cancelling counting task now")
                    counting_task.cancel()

        async def keepalive_coro():
            while True:
                await asyncio.sleep(5 * MS)
                try:
                    await WebSocketServerHelper.send_keepalive(ws)
                except websockets.exceptions.ConnectionClosed:
                    break

        stopping_task = asyncio.ensure_future(stopping_coro())
        if WITH_KEEPALIVE:
            keepalive_task = asyncio.ensure_future(keepalive_coro())

        try:
            await counting_task
        except asyncio.CancelledError:
            print("Now counting task is cancelled")
        except Exception as exc:
            print(f"Exception in counting task: {exc!s}")

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
        await WebSocketServerHelper.wait_connection_terminate(ws)
    except websockets.exceptions.ConnectionClosedOK:
        pass
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
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_subscription(
    aiohttp_client_and_server, subscription_str
):

    session, server = aiohttp_client_and_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async for result in session.subscribe(subscription):

        number = result["number"]
        print(f"Number received: {number}")

        assert number == count
        count -= 1

    assert count == -1


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_subscription_get_execution_result(
    aiohttp_client_and_server, subscription_str
):

    session, server = aiohttp_client_and_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async for result in session.subscribe(subscription, get_execution_result=True):

        assert isinstance(result, ExecutionResult)
        assert result.data is not None

        number = result.data["number"]
        print(f"Number received: {number}")

        assert number == count
        count -= 1

    assert count == -1


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_subscription_break(
    aiohttp_client_and_server, subscription_str
):

    session, server = aiohttp_client_and_server

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
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_subscription_task_cancel(
    aiohttp_client_and_server, subscription_str
):

    session, server = aiohttp_client_and_server

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

        await asyncio.sleep(11 * MS)

        task.cancel()

    cancel_task = asyncio.ensure_future(cancel_task_coro())

    await asyncio.gather(task, cancel_task)

    assert count > 0
    assert task_cancelled is True


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_subscription_close_transport(
    aiohttp_client_and_server, subscription_str
):

    session, _ = aiohttp_client_and_server

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

        await asyncio.sleep(11 * MS)

        await session.transport.close()

    close_transport_task = asyncio.ensure_future(close_transport_task_coro())

    await asyncio.gather(task, close_transport_task)

    assert count > 0


async def server_countdown_close_connection_in_middle(ws):
    await WebSocketServerHelper.send_connection_ack(ws)

    result = await ws.recv()
    json_result = json.loads(result)
    assert json_result["type"] == "start"
    payload = json_result["payload"]
    query = payload["query"]
    query_id = json_result["id"]

    count_found = search("count: {:d}", query)
    count = count_found[0]
    stopping_before = count // 2
    print(f"Countdown started from: {count}, stopping server before {stopping_before}")
    for number in range(count, stopping_before, -1):
        await ws.send(countdown_server_answer.format(query_id=query_id, number=number))
        await asyncio.sleep(2 * MS)

    print("Closing server while subscription is still running now")
    await ws.close()
    await ws.wait_closed()
    print("Server is now closed")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "server", [server_countdown_close_connection_in_middle], indirect=True
)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_subscription_server_connection_closed(
    aiohttp_client_and_server, subscription_str
):

    session, server = aiohttp_client_and_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    with pytest.raises(TransportConnectionFailed):

        async for result in session.subscribe(subscription):

            number = result["number"]
            print(f"Number received: {number}")

            assert number == count

            count -= 1


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_subscription_slow_consumer(
    aiohttp_client_and_server, subscription_str
):

    session, server = aiohttp_client_and_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async for result in session.subscribe(subscription):
        await asyncio.sleep(10 * MS)

        number = result["number"]
        print(f"Number received: {number}")

        assert number == count

        count -= 1

    assert count == -1


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_subscription_with_operation_name(
    aiohttp_client_and_server, subscription_str
):

    session, server = aiohttp_client_and_server

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


WITH_KEEPALIVE = True


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_subscription_with_keepalive(
    aiohttp_client_and_server, subscription_str
):

    session, server = aiohttp_client_and_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async for result in session.subscribe(subscription):

        number = result["number"]
        print(f"Number received: {number}")

        assert number == count
        count -= 1

    assert count == -1


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_subscription_with_keepalive_with_timeout_ok(
    server, subscription_str
):

    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"
    transport = AIOHTTPWebsocketsTransport(url=url, keep_alive_timeout=(20 * MS))

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
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_subscription_with_keepalive_with_timeout_nok(
    server, subscription_str
):

    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"
    transport = AIOHTTPWebsocketsTransport(url=url, keep_alive_timeout=(1 * MS))

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


@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
def test_aiohttp_websocket_subscription_sync(server, subscription_str):
    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    url = f"ws://{server.hostname}:{server.port}/graphql"
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


@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
def test_aiohttp_websocket_subscription_sync_user_exception(server, subscription_str):
    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    url = f"ws://{server.hostname}:{server.port}/graphql"
    print(f"url = {url}")

    transport = AIOHTTPWebsocketsTransport(url=url)

    client = Client(transport=transport)

    count = 10
    subscription = gql(subscription_str.format(count=count))

    with pytest.raises(Exception) as exc_info:
        for result in client.subscribe(subscription):

            number = result["number"]
            print(f"Number received: {number}")

            assert number == count
            count -= 1

            if count == 5:
                raise Exception("This is an user exception")

    assert count == 5
    assert "This is an user exception" in str(exc_info.value)


@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
def test_aiohttp_websocket_subscription_sync_break(server, subscription_str):
    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    url = f"ws://{server.hostname}:{server.port}/graphql"
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

        if count == 5:
            break

    assert count == 5


@pytest.mark.skipif(sys.platform.startswith("win"), reason="test failing on windows")
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
def test_aiohttp_websocket_subscription_sync_graceful_shutdown(
    server, subscription_str
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

    url = f"ws://{server.hostname}:{server.port}/graphql"
    print(f"url = {url}")

    transport = AIOHTTPWebsocketsTransport(url=url)

    client = Client(transport=transport)

    count = 10
    subscription = gql(subscription_str.format(count=count))

    interrupt_task = None

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
                    interrupt_task = asyncio.ensure_future(
                        client.session._generator.athrow(KeyboardInterrupt)
                    )

            count -= 1

    assert count == 4

    # Catch interrupt_task exception to remove warning
    assert interrupt_task is not None
    interrupt_task.exception()

    # Check that the server received a connection_terminate message last
    assert logged_messages.pop() == '{"type": "connection_terminate"}'


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_aiohttp_websocket_subscription_running_in_thread(
    server, subscription_str, run_sync_test
):
    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    def test_code():
        path = "/graphql"
        url = f"ws://{server.hostname}:{server.port}{path}"
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

    await run_sync_test(server, test_code)


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_starwars], indirect=True)
@pytest.mark.parametrize("subscription_str", [starwars_subscription_str])
@pytest.mark.parametrize(
    "client_params",
    [
        {"schema": StarWarsSchema},
        {"introspection": StarWarsIntrospection},
        {"schema": StarWarsTypeDef},
    ],
)
async def test_async_aiohttp_client_validation(server, subscription_str, client_params):

    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    url = f"ws://{server.hostname}:{server.port}/graphql"

    transport = AIOHTTPWebsocketsTransport(url=url)

    client = Client(transport=transport, **client_params)

    async with client as session:

        subscription = gql(subscription_str)

        subscription.variable_values = {"ep": "JEDI"}

        expected = []

        async for result in session.subscribe(subscription, parse_result=False):

            review = result["reviewAdded"]
            expected.append(review)

            assert "stars" in review
            assert "commentary" in review
            assert "episode" in review

        assert expected[0] == starwars_expected_one


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_subscribe_on_closing_transport(server, subscription_str):

    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    url = f"ws://{server.hostname}:{server.port}/graphql"

    transport = AIOHTTPWebsocketsTransport(url=url)

    client = Client(transport=transport)
    count = 1
    subscription = gql(subscription_str.format(count=count))

    async with client as session:
        session.transport.adapter.websocket._writer._closing = True

        with pytest.raises(TransportConnectionFailed):
            async for _ in session.subscribe(subscription):
                pass


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_subscribe_on_null_transport(server, subscription_str):

    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    url = f"ws://{server.hostname}:{server.port}/graphql"

    transport = AIOHTTPWebsocketsTransport(url=url)

    client = Client(transport=transport)
    count = 1
    subscription = gql(subscription_str.format(count=count))

    async with client as session:

        session.transport.adapter.websocket = None
        with pytest.raises(TransportConnectionFailed):
            async for _ in session.subscribe(subscription):
                pass
