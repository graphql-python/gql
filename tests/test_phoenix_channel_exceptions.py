import pytest

from gql import Client, gql
from gql.transport.exceptions import (
    TransportProtocolError,
    TransportQueryError,
    TransportServerError,
)

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

default_subscription_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"response":'
    '{"subscriptionId":"test_subscription"},'
    '"status":"ok"},'
    '"ref":2,'
    '"topic":"test_topic"}'
)

error_with_reason_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"response":'
    '{"reason":"internal error"},'
    '"status":"error"},'
    '"ref":2,'
    '"topic":"test_topic"}'
)

multiple_errors_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"response":'
    '{"errors": ["error 1", "error 2"]},'
    '"status":"error"},'
    '"ref":2,'
    '"topic":"test_topic"}'
)

timeout_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"status":"timeout"},'
    '"ref":2,'
    '"topic":"test_topic"}'
)


def server(
    query_server_answer, subscription_server_answer=default_subscription_server_answer,
):
    from .conftest import PhoenixChannelServerHelper

    async def phoenix_server(ws, path):
        await PhoenixChannelServerHelper.send_connection_ack(ws)
        await ws.recv()
        await ws.send(subscription_server_answer)
        if query_server_answer is not None:
            await ws.send(query_server_answer)
        await PhoenixChannelServerHelper.send_close(ws)
        await ws.wait_closed()

    return phoenix_server


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "server",
    [
        server(error_with_reason_server_answer),
        server(multiple_errors_server_answer),
        server(timeout_server_answer),
    ],
    indirect=True,
)
@pytest.mark.parametrize("query_str", [query1_str])
async def test_phoenix_channel_query_error(event_loop, server, query_str):

    from gql.transport.phoenix_channel_websockets import (
        PhoenixChannelWebsocketsTransport,
    )

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"
    sample_transport = PhoenixChannelWebsocketsTransport(
        channel_name="test_channel", url=url
    )

    query = gql(query_str)
    with pytest.raises(TransportQueryError):
        async with Client(transport=sample_transport) as session:
            await session.execute(query)


invalid_subscription_id_server_answer = (
    '{"event":"subscription:data","payload":'
    '{"subscriptionId":"INVALID","result":'
    '{"data":{"continents":['
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
    '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
    '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
    '{"code":"SA","name":"South America"}]}}},'
    '"ref":3,'
    '"topic":"test_topic"}'
)

invalid_payload_server_answer = (
    '{"event":"subscription:data",'
    '"payload":"INVALID",'
    '"ref":3,'
    '"topic":"test_topic"}'
)

invalid_result_server_answer = (
    '{"event":"subscription:data","payload":'
    '{"subscriptionId":"test_subscription","result": "INVALID"},'
    '"ref":3,'
    '"topic":"test_topic"}'
)

generic_error_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"status":"error"},'
    '"ref":2,'
    '"topic":"test_topic"}'
)

protocol_server_answer = '{"event":"unknown"}'

invalid_payload_subscription_server_answer = (
    '{"event":"phx_reply", "payload":"INVALID", "ref":2, "topic":"test_topic"}'
)


async def no_connection_ack_phoenix_server(ws, path):
    from .conftest import PhoenixChannelServerHelper

    await ws.recv()
    await PhoenixChannelServerHelper.send_close(ws)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "server",
    [
        server(invalid_subscription_id_server_answer),
        server(invalid_result_server_answer),
        server(generic_error_server_answer),
        no_connection_ack_phoenix_server,
        server(protocol_server_answer),
        server(invalid_payload_server_answer),
        server(None, invalid_payload_subscription_server_answer),
    ],
    indirect=True,
)
@pytest.mark.parametrize("query_str", [query1_str])
async def test_phoenix_channel_protocol_error(event_loop, server, query_str):

    from gql.transport.phoenix_channel_websockets import (
        PhoenixChannelWebsocketsTransport,
    )

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"
    sample_transport = PhoenixChannelWebsocketsTransport(
        channel_name="test_channel", url=url
    )

    query = gql(query_str)
    with pytest.raises(TransportProtocolError):
        async with Client(transport=sample_transport) as session:
            await session.execute(query)


server_error_subscription_server_answer = (
    '{"event":"phx_error", "ref":2, "topic":"test_topic"}'
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "server", [server(None, server_error_subscription_server_answer)], indirect=True,
)
@pytest.mark.parametrize("query_str", [query1_str])
async def test_phoenix_channel_server_error(event_loop, server, query_str):

    from gql.transport.phoenix_channel_websockets import (
        PhoenixChannelWebsocketsTransport,
    )

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"
    sample_transport = PhoenixChannelWebsocketsTransport(
        channel_name="test_channel", url=url
    )

    query = gql(query_str)
    with pytest.raises(TransportServerError):
        async with Client(transport=sample_transport) as session:
            await session.execute(query)
