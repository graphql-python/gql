import asyncio
import json

import pytest
import websockets
from parse import search

from gql import Client, gql
from gql.transport.phoenix_channel_websockets import PhoenixChannelWebsocketsTransport

from .conftest import MS, PhoenixChannelServerHelper

subscription_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"response":'
    '{"subscriptionId":"test_subscription"},'
    '"status":"ok"},'
    '"ref":2,'
    '"topic":"test_topic"}'
)

countdown_server_answer = (
    '{{"event":"subscription:data",'
    '"payload":{{"subscriptionId":"test_subscription","result":'
    '{{"data":{{"number":{number}}}}}}},'
    '"ref":{query_id}}}'
)


async def server_countdown(ws, path):
    try:
        await PhoenixChannelServerHelper.send_connection_ack(ws)

        result = await ws.recv()
        json_result = json.loads(result)
        assert json_result["event"] == "doc"
        payload = json_result["payload"]
        query = payload["query"]
        query_id = json_result["ref"]

        count_found = search("count: {:d}", query)
        count = count_found[0]
        print(f"Countdown started from: {count}")

        await ws.send(subscription_server_answer)

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

        await PhoenixChannelServerHelper.send_close(ws)
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
async def test_phoenix_channel_subscription(event_loop, server, subscription_str):

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"
    sample_transport = PhoenixChannelWebsocketsTransport(
        channel_name="test_channel", url=url
    )

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async with Client(transport=sample_transport) as session:
        async for result in session.subscribe(subscription):

            number = result["number"]
            print(f"Number received: {number}")

            assert number == count
            count -= 1

    assert count == -1


heartbeat_server_answer = (
    '{{"event":"subscription:data",'
    '"payload":{{"subscriptionId":"test_subscription","result":'
    '{{"data":{{"heartbeat_count":{count}}}}}}},'
    '"ref":1}}'
)


async def phoenix_heartbeat_server(ws, path):
    await PhoenixChannelServerHelper.send_connection_ack(ws)
    await ws.recv()
    await ws.send(subscription_server_answer)

    for i in range(3):
        heartbeat_result = await ws.recv()
        json_result = json.loads(heartbeat_result)
        assert json_result["event"] == "heartbeat"
        await ws.send(heartbeat_server_answer.format(count=i))

    await PhoenixChannelServerHelper.send_close(ws)
    await ws.wait_closed()


heartbeat_subscription_str = """
    subscription {
      heartbeat {
        heartbeat_count
      }
    }
"""


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [phoenix_heartbeat_server], indirect=True)
@pytest.mark.parametrize("subscription_str", [heartbeat_subscription_str])
async def test_phoenix_channel_heartbeat(event_loop, server, subscription_str):

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"
    sample_transport = PhoenixChannelWebsocketsTransport(
        channel_name="test_channel", url=url, heartbeat_interval=1
    )

    subscription = gql(heartbeat_subscription_str)
    async with Client(transport=sample_transport) as session:
        i = 0
        async for result in session.subscribe(subscription):
            heartbeat_count = result["heartbeat_count"]
            print(f"Heartbeat count received: {heartbeat_count}")

            assert heartbeat_count == i
            i += 1
