import asyncio
import json
import sys

import pytest
from parse import search

from gql import Client, gql

# Marking all tests in this file with the websockets marker
pytestmark = pytest.mark.websockets

test_channel = "test_channel"
test_subscription_id = "test_subscription"

# A server should send this after receiving a 'phx_leave' request message.
# 'query_id' should be the value of the 'ref' in the 'phx_leave' request.
# With only one listener, the transport is closed automatically when
# it exits a subscription, so this is not used in current tests.
channel_leave_reply_template = (
    "{{"
    '"topic":"{channel_name}",'
    '"event":"phx_reply",'
    '"payload":{{'
    '"response":{{}},'
    '"status":"ok"'
    "}},"
    '"ref":{query_id}'
    "}}"
)

# A server should send this after sending the 'channel_leave_reply'
# above, to confirm to the client that the channel was actually closed.
# With only one listener, the transport is closed automatically when
# it exits a subscription, so this is not used in current tests.
channel_close_reply_template = (
    "{{"
    '"topic":"{channel_name}",'
    '"event":"phx_close",'
    '"payload":{{}},'
    '"ref":null'
    "}}"
)

# A server sends this when it receives a 'subscribe' request,
# after creating a unique subscription id. 'query_id' should be the
# value of the 'ref' in the 'subscribe' request.
subscription_reply_template = (
    "{{"
    '"topic":"{channel_name}",'
    '"event":"phx_reply",'
    '"payload":{{'
    '"response":{{'
    '"subscriptionId":"{subscription_id}"'
    "}},"
    '"status":"ok"'
    "}},"
    '"ref":{query_id}'
    "}}"
)

countdown_data_template = (
    "{{"
    '"topic":"{subscription_id}",'
    '"event":"subscription:data",'
    '"payload":{{'
    '"subscriptionId":"{subscription_id}",'
    '"result":{{'
    '"data":{{'
    '"countdown":{{'
    '"number":{number}'
    "}}"
    "}}"
    "}}"
    "}},"
    '"ref":null'
    "}}"
)


async def server_countdown(ws, path):
    import websockets

    from .conftest import MS, PhoenixChannelServerHelper

    try:
        await PhoenixChannelServerHelper.send_connection_ack(ws)

        result = await ws.recv()
        json_result = json.loads(result)
        assert json_result["event"] == "doc"
        channel_name = json_result["topic"]
        query_id = json_result["ref"]

        payload = json_result["payload"]
        query = payload["query"]
        count_found = search("count: {:d}", query)
        count = count_found[0]
        print(f"Countdown started from: {count}")

        await ws.send(
            subscription_reply_template.format(
                subscription_id=test_subscription_id,
                channel_name=channel_name,
                query_id=query_id,
            )
        )

        async def counting_coro():
            for number in range(count, -1, -1):
                await ws.send(
                    countdown_data_template.format(
                        subscription_id=test_subscription_id, number=number
                    )
                )
                await asyncio.sleep(2 * MS)

        counting_task = asyncio.ensure_future(counting_coro())

        async def stopping_coro():
            nonlocal counting_task
            while True:
                result = await ws.recv()
                json_result = json.loads(result)

                if json_result["event"] == "unsubscribe":
                    query_id = json_result["ref"]
                    payload = json_result["payload"]
                    subscription_id = payload["subscriptionId"]
                    assert subscription_id == test_subscription_id

                    print("Sending unsubscribe reply")
                    await ws.send(
                        subscription_reply_template.format(
                            subscription_id=subscription_id,
                            channel_name=channel_name,
                            query_id=query_id,
                        )
                    )
                    counting_task.cancel()

        stopping_task = asyncio.ensure_future(stopping_coro())

        try:
            await counting_task
        except asyncio.CancelledError:
            print("Now counting task is cancelled")

        # Waiting for a clean stop
        try:
            await asyncio.wait_for(stopping_task, 3)
        except asyncio.CancelledError:
            print("Now stopping task is cancelled")
        except asyncio.TimeoutError:
            print("Now stopping task is in timeout")

        # await PhoenixChannelServerHelper.send_close(ws)
    except websockets.exceptions.ConnectionClosedOK:
        print("Connection closed")
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
@pytest.mark.parametrize("end_count", [0, 5])
async def test_phoenix_channel_subscription(
    event_loop, server, subscription_str, end_count
):
    """Parameterized test.

    :param end_count: Target count at which the test will 'break' to unsubscribe.
    """
    import logging

    from gql.transport.phoenix_channel_websockets import (
        PhoenixChannelWebsocketsTransport,
    )
    from gql.transport.phoenix_channel_websockets import log as phoenix_logger
    from gql.transport.websockets import log as websockets_logger

    websockets_logger.setLevel(logging.DEBUG)
    phoenix_logger.setLevel(logging.DEBUG)

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"
    sample_transport = PhoenixChannelWebsocketsTransport(
        channel_name=test_channel, url=url, close_timeout=5
    )

    count = 10
    subscription = gql(subscription_str.format(count=count))

    async with Client(transport=sample_transport) as session:
        async for result in session.subscribe(subscription):
            number = result["countdown"]["number"]
            print(f"Number received: {number}")

            assert number == count
            if number == end_count:
                # Note: we need to run generator.aclose() here or the finally block in
                # the subscribe will not be reached in pypy3 (python version 3.6.1)
                # In more recent versions, 'break' will trigger __aexit__.
                if sys.version_info < (3, 7):
                    await session._generator.aclose()
                print("break")
                break

            count -= 1

    assert count == end_count


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_countdown], indirect=True)
@pytest.mark.parametrize("subscription_str", [countdown_subscription_str])
async def test_phoenix_channel_subscription_no_break(
    event_loop, server, subscription_str
):
    import logging

    from gql.transport.phoenix_channel_websockets import (
        PhoenixChannelWebsocketsTransport,
    )
    from gql.transport.phoenix_channel_websockets import log as phoenix_logger
    from gql.transport.websockets import log as websockets_logger

    from .conftest import MS

    websockets_logger.setLevel(logging.DEBUG)
    phoenix_logger.setLevel(logging.DEBUG)

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"

    async def testing_stopping_without_break():

        sample_transport = PhoenixChannelWebsocketsTransport(
            channel_name=test_channel, url=url, close_timeout=(5000 * MS)
        )

        count = 10
        subscription = gql(subscription_str.format(count=count))

        async with Client(transport=sample_transport) as session:
            async for result in session.subscribe(subscription):
                number = result["countdown"]["number"]
                print(f"Number received: {number}")

                # Simulate a slow consumer
                if number == 10:
                    await asyncio.sleep(50 * MS)

                if number == 9:
                    # When we consume the number 9 here in the async generator,
                    # all the 10 numbers have already been sent by the backend and
                    # are present in the listener queue
                    # we simulate here an unsubscribe message
                    # In that case, all the 10 numbers should be consumed in the
                    # generator and then the generator should be closed properly
                    await session.transport._send_stop_message(2)

                assert number == count

                count -= 1

        assert count == -1

    try:
        await asyncio.wait_for(testing_stopping_without_break(), timeout=(5000 * MS))
    except asyncio.TimeoutError:
        assert False, "The async generator did not stop"


heartbeat_data_template = (
    "{{"
    '"topic":"{subscription_id}",'
    '"event":"subscription:data",'
    '"payload":{{'
    '"subscriptionId":"{subscription_id}",'
    '"result":{{'
    '"data":{{'
    '"heartbeat":{{'
    '"heartbeat_count":{count}'
    "}}"
    "}}"
    "}}"
    "}},"
    '"ref":null'
    "}}"
)


async def phoenix_heartbeat_server(ws, path):
    import websockets

    from .conftest import PhoenixChannelServerHelper

    try:
        await PhoenixChannelServerHelper.send_connection_ack(ws)

        result = await ws.recv()
        json_result = json.loads(result)
        assert json_result["event"] == "doc"
        channel_name = json_result["topic"]
        query_id = json_result["ref"]

        await ws.send(
            subscription_reply_template.format(
                subscription_id=test_subscription_id,
                channel_name=channel_name,
                query_id=query_id,
            )
        )

        async def heartbeat_coro():
            i = 0
            while True:
                heartbeat_result = await ws.recv()
                json_result = json.loads(heartbeat_result)
                if json_result["event"] == "heartbeat":
                    await ws.send(
                        heartbeat_data_template.format(
                            subscription_id=test_subscription_id, count=i
                        )
                    )
                    i = i + 1
                elif json_result["event"] == "unsubscribe":
                    query_id = json_result["ref"]
                    payload = json_result["payload"]
                    subscription_id = payload["subscriptionId"]
                    assert subscription_id == test_subscription_id

                    print("Sending unsubscribe reply")
                    await ws.send(
                        subscription_reply_template.format(
                            subscription_id=subscription_id,
                            channel_name=channel_name,
                            query_id=query_id,
                        )
                    )

        await asyncio.wait_for(heartbeat_coro(), 60)
        # await PhoenixChannelServerHelper.send_close(ws)
    except websockets.exceptions.ConnectionClosedOK:
        print("Connection closed")
    finally:
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
    from gql.transport.phoenix_channel_websockets import (
        PhoenixChannelWebsocketsTransport,
    )

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"
    sample_transport = PhoenixChannelWebsocketsTransport(
        channel_name=test_channel, url=url, heartbeat_interval=0.1
    )

    subscription = gql(heartbeat_subscription_str)
    async with Client(transport=sample_transport) as session:
        i = 0
        async for result in session.subscribe(subscription):
            heartbeat_count = result["heartbeat"]["heartbeat_count"]
            print(f"Heartbeat count received: {heartbeat_count}")

            assert heartbeat_count == i
            if heartbeat_count == 5:
                # Note: we need to run generator.aclose() here or the finally block in
                # the subscribe will not be reached in pypy3 (python version 3.6.1)
                # In more recent versions, 'break' will trigger __aexit__.
                if sys.version_info < (3, 7):
                    await session._generator.aclose()
                break

            i += 1
