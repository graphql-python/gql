import asyncio
import pytest
import json
import websockets

from parse import search
from .websocket_fixtures import MS, server, client_and_server, TestServer
from graphql.execution import ExecutionResult
from gql import gql


countdown_server_answer = (
    '{{"type":"data","id":"{query_id}","payload":{{"data":{{"number":{number}}}}}}}'
)

WITH_KEEPALIVE = False


async def server_countdown(ws, path):
    global WITH_KEEPALIVE
    try:
        await TestServer.send_connection_ack(ws)
        if WITH_KEEPALIVE:
            await TestServer.send_keepalive(ws)

        result = await ws.recv()
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

                result = await ws.recv()
                json_result = json.loads(result)

                if json_result["type"] == "stop" and json_result["id"] == str(query_id):
                    print("Cancelling counting task now")
                    counting_task.cancel()

        async def keepalive_coro():
            while True:
                await asyncio.sleep(5 * MS)
                await TestServer.send_keepalive(ws)

        stopping_task = asyncio.ensure_future(stopping_coro())
        keepalive_task = asyncio.ensure_future(keepalive_coro())

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

        await TestServer.send_complete(ws, query_id)
        await TestServer.wait_connection_terminate(ws)
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
async def test_websocket_subscription(client_and_server, subscription_str):

    client, server = client_and_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async for result in client.subscribe(subscription):
        assert isinstance(result, ExecutionResult)

        number = result.data["number"]
        print(f"Number received: {number}")

        assert number == count
        count -= 1

    assert count == -1


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_websocket_subscription_break(client_and_server, subscription_str):

    client, server = client_and_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async for result in client.subscribe(subscription):
        assert isinstance(result, ExecutionResult)

        number = result.data["number"]
        print(f"Number received: {number}")

        assert number == count

        if count <= 5:
            break

        count -= 1

    assert count == 5


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_websocket_subscription_task_cancel(client_and_server, subscription_str):

    client, server = client_and_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async def task_coro():
        nonlocal count
        async for result in client.subscribe(subscription):
            assert isinstance(result, ExecutionResult)

            number = result.data["number"]
            print(f"Number received: {number}")

            assert number == count

            count -= 1

    task = asyncio.ensure_future(task_coro())

    async def cancel_task_coro():
        nonlocal task

        await asyncio.sleep(11 * MS)

        task.cancel()

    cancel_task = asyncio.ensure_future(cancel_task_coro())

    await asyncio.gather(task, cancel_task)

    assert count > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_websocket_subscription_close_transport(
    client_and_server, subscription_str
):

    client, server = client_and_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async def task_coro():
        nonlocal count
        async for result in client.subscribe(subscription):
            assert isinstance(result, ExecutionResult)

            number = result.data["number"]
            print(f"Number received: {number}")

            assert number == count

            count -= 1

    task = asyncio.ensure_future(task_coro())

    async def close_transport_task_coro():
        nonlocal task

        await asyncio.sleep(11 * MS)

        await client.transport.close()

    close_transport_task = asyncio.ensure_future(close_transport_task_coro())

    await asyncio.gather(task, close_transport_task)

    assert count > 0


async def server_countdown_close_connection_in_middle(ws, path):
    await TestServer.send_connection_ack(ws)

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
async def test_websocket_subscription_server_connection_closed(
    client_and_server, subscription_str
):

    client, server = client_and_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    with pytest.raises(websockets.exceptions.ConnectionClosedOK):

        async for result in client.subscribe(subscription):
            assert isinstance(result, ExecutionResult)

            number = result.data["number"]
            print(f"Number received: {number}")

            assert number == count

            count -= 1

        assert count > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_websocket_subscription_slow_consumer(
    client_and_server, subscription_str
):

    client, server = client_and_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async for result in client.subscribe(subscription):
        await asyncio.sleep(10 * MS)
        assert isinstance(result, ExecutionResult)

        number = result.data["number"]
        print(f"Number received: {number}")

        assert number == count

        count -= 1

    assert count == -1


WITH_KEEPALIVE = True


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_websocket_subscription_with_keepalive(
    client_and_server, subscription_str
):

    client, server = client_and_server

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async for result in client.subscribe(subscription):
        assert isinstance(result, ExecutionResult)

        number = result.data["number"]
        print(f"Number received: {number}")

        assert number == count
        count -= 1

    assert count == -1
