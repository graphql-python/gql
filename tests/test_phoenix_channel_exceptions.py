import pytest

from gql import Client, gql
from gql.transport.exceptions import TransportProtocolError, TransportQueryError
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


error_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"response":'
    '{"reason":"internal error"},'
    '"status":"error"},'
    '"ref":2,'
    '"topic":"test_topic"}'
)


async def phoenix_server_reply_error(ws, path):
    await PhoenixChannelServerHelper.send_connection_ack(ws)
    await ws.recv()
    await ws.send(subscription_server_answer)
    await ws.send(error_server_answer)
    await PhoenixChannelServerHelper.send_close(ws)
    await ws.wait_closed()


timeout_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"status":"timeout"},'
    '"ref":2,'
    '"topic":"test_topic"}'
)


async def phoenix_server_timeout(ws, path):
    await PhoenixChannelServerHelper.send_connection_ack(ws)
    await ws.recv()
    await ws.send(subscription_server_answer)
    await ws.send(timeout_server_answer)
    await PhoenixChannelServerHelper.send_close(ws)
    await ws.wait_closed()


generic_error_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"status":"error"},'
    '"ref":2,'
    '"topic":"test_topic"}'
)


async def phoenix_server_generic_error(ws, path):
    await PhoenixChannelServerHelper.send_connection_ack(ws)
    await ws.recv()
    await ws.send(subscription_server_answer)
    await ws.send(generic_error_server_answer)
    await PhoenixChannelServerHelper.send_close(ws)
    await ws.wait_closed()


protocol_server_answer = '{"event":"unknown"}'


async def phoenix_server_protocol_error(ws, path):
    await PhoenixChannelServerHelper.send_connection_ack(ws)
    await ws.recv()
    await ws.send(subscription_server_answer)
    await ws.send(protocol_server_answer)
    await PhoenixChannelServerHelper.send_close(ws)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "server", [phoenix_server_reply_error, phoenix_server_timeout], indirect=True
)
@pytest.mark.parametrize("query_str", [query1_str])
async def test_phoenix_channel_query_error(event_loop, server, query_str):

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"
    sample_transport = PhoenixChannelWebsocketsTransport(
        channel_name="test_channel", url=url
    )

    query = gql(query_str)
    with pytest.raises(TransportQueryError):
        async with Client(transport=sample_transport) as session:
            await session.execute(query)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "server",
    [phoenix_server_generic_error, phoenix_server_protocol_error],
    indirect=True,
)
@pytest.mark.parametrize("query_str", [query1_str])
async def test_phoenix_channel_protocol_error(event_loop, server, query_str):

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"
    sample_transport = PhoenixChannelWebsocketsTransport(
        channel_name="test_channel", url=url
    )

    query = gql(query_str)
    with pytest.raises(TransportProtocolError):
        async with Client(transport=sample_transport) as session:
            await session.execute(query)
