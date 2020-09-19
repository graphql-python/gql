import pytest

from gql import Client, gql
from gql.transport.phoenix_channel_websockets import PhoenixChannelWebsocketsTransport

from .conftest import PhoenixChannelServerHelper

query1_str = """
    query getContinents {
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

query1_server_answer = (
    '{"event":"subscription:data","payload":'
    '{"subscriptionId":"test_subscription","result":'
    '{"data":{"continents":['
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
    '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
    '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
    '{"code":"SA","name":"South America"}]}}},'
    '"ref":3,'
    '"topic":"test_topic"}'
)


@pytest.fixture
def ws_server_helper(request):
    yield PhoenixChannelServerHelper


async def phoenix_server(ws, path):
    await PhoenixChannelServerHelper.send_connection_ack(ws)
    await ws.recv()
    await ws.send(subscription_server_answer)
    await ws.send(query1_server_answer)
    await PhoenixChannelServerHelper.send_close(ws)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [phoenix_server], indirect=True)
@pytest.mark.parametrize("query_str", [query1_str])
async def test_phoenix_channel_simple_query(event_loop, server, query_str):

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"
    sample_transport = PhoenixChannelWebsocketsTransport(
        channel_name="test_channel", url=url
    )

    query = gql(query_str)
    async with Client(transport=sample_transport) as session:
        result = await session.execute(query)

    print("Client received:", result)
