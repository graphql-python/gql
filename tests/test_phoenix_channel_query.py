import pytest

from gql import Client, gql

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

default_query_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"response":'
    '{"data":{"continents":['
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
    '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
    '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
    '{"code":"SA","name":"South America"}]}},'
    '"status":"ok"},'
    '"ref":2,'
    '"topic":"test_topic"}'
)


@pytest.fixture
def ws_server_helper(request):
    from .conftest import PhoenixChannelServerHelper

    yield PhoenixChannelServerHelper


async def query_server(ws, path):
    from .conftest import PhoenixChannelServerHelper

    await PhoenixChannelServerHelper.send_connection_ack(ws)
    await ws.recv()
    await ws.send(default_query_server_answer)
    await PhoenixChannelServerHelper.send_close(ws)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [query_server], indirect=True)
@pytest.mark.parametrize("query_str", [query1_str])
async def test_phoenix_channel_query(event_loop, server, query_str):
    from gql.transport.phoenix_channel_websockets import (
        PhoenixChannelWebsocketsTransport,
    )

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"
    sample_transport = PhoenixChannelWebsocketsTransport(
        channel_name="test_channel", url=url
    )

    query = gql(query_str)
    async with Client(transport=sample_transport) as session:
        result = await session.execute(query)

    print("Client received:", result)


query2_str = """
    subscription getContinents {
      continents {
        code
        name
      }
    }
"""

subscription_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"response":'
    '{"subscriptionId":"test_subscription"},'
    '"status":"ok"},'
    '"ref":2,'
    '"topic":"test_topic"}'
)

subscription_data_server_answer = (
    '{"event":"subscription:data","payload":'
    '{"subscriptionId":"test_subscription","result":'
    '{"data":{"continents":['
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
    '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
    '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
    '{"code":"SA","name":"South America"}]}}},'
    '"ref":null,'
    '"topic":"test_subscription"}'
)

unsubscribe_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"response":'
    '{"subscriptionId":"test_subscription"},'
    '"status":"ok"},'
    '"ref":3,'
    '"topic":"test_topic"}'
)


async def subscription_server(ws, path):
    from .conftest import PhoenixChannelServerHelper

    await PhoenixChannelServerHelper.send_connection_ack(ws)
    await ws.recv()
    await ws.send(subscription_server_answer)
    await ws.send(subscription_data_server_answer)
    await ws.recv()
    await ws.send(unsubscribe_server_answer)
    # Unsubscribe will remove the listener
    # await PhoenixChannelServerHelper.send_close(ws)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [subscription_server], indirect=True)
@pytest.mark.parametrize("query_str", [query2_str])
async def test_phoenix_channel_subscription(event_loop, server, query_str):
    from gql.transport.phoenix_channel_websockets import (
        PhoenixChannelWebsocketsTransport,
    )

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"
    sample_transport = PhoenixChannelWebsocketsTransport(
        channel_name="test_channel", url=url
    )

    first_result = None
    query = gql(query_str)
    async with Client(transport=sample_transport) as session:
        async for result in session.subscribe(query):
            first_result = result
            break

    print("Client received:", first_result)
