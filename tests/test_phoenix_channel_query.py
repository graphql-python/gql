import pytest

from gql import Client, gql

from .conftest import get_localhost_ssl_context_client

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


async def query_server(ws):
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
    transport = PhoenixChannelWebsocketsTransport(channel_name="test_channel", url=url)

    query = gql(query_str)
    async with Client(transport=transport) as session:
        result = await session.execute(query)

    print("Client received:", result)


@pytest.mark.skip(reason="ssl=False is not working for now")
@pytest.mark.asyncio
@pytest.mark.parametrize("ws_ssl_server", [query_server], indirect=True)
@pytest.mark.parametrize("query_str", [query1_str])
@pytest.mark.parametrize("verify_https", ["disabled", "cert_provided"])
async def test_phoenix_channel_query_ssl(
    event_loop, ws_ssl_server, query_str, verify_https
):
    from gql.transport.phoenix_channel_websockets import (
        PhoenixChannelWebsocketsTransport,
    )

    path = "/graphql"
    server = ws_ssl_server
    url = f"wss://{server.hostname}:{server.port}{path}"

    extra_args = {}

    if verify_https == "cert_provided":
        _, ssl_context = get_localhost_ssl_context_client()

        extra_args["ssl"] = ssl_context
    elif verify_https == "disabled":
        extra_args["ssl"] = False

    transport = PhoenixChannelWebsocketsTransport(
        channel_name="test_channel",
        url=url,
        **extra_args,
    )

    query = gql(query_str)
    async with Client(transport=transport) as session:
        result = await session.execute(query)

    print("Client received:", result)


@pytest.mark.asyncio
@pytest.mark.parametrize("ws_ssl_server", [query_server], indirect=True)
@pytest.mark.parametrize("query_str", [query1_str])
@pytest.mark.parametrize("verify_https", ["explicitely_enabled", "default"])
async def test_phoenix_channel_query_ssl_self_cert_fail(
    event_loop, ws_ssl_server, query_str, verify_https
):
    from gql.transport.phoenix_channel_websockets import (
        PhoenixChannelWebsocketsTransport,
    )
    from ssl import SSLCertVerificationError

    path = "/graphql"
    server = ws_ssl_server
    url = f"wss://{server.hostname}:{server.port}{path}"

    extra_args = {}

    if verify_https == "explicitely_enabled":
        extra_args["ssl"] = True

    transport = PhoenixChannelWebsocketsTransport(
        channel_name="test_channel",
        url=url,
        **extra_args,
    )

    query = gql(query_str)

    with pytest.raises(SSLCertVerificationError) as exc_info:
        async with Client(transport=transport) as session:
            await session.execute(query)

    expected_error = "certificate verify failed: self-signed certificate"

    assert expected_error in str(exc_info.value)


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


async def subscription_server(ws):
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
    transport = PhoenixChannelWebsocketsTransport(channel_name="test_channel", url=url)

    first_result = None
    query = gql(query_str)
    async with Client(transport=transport) as session:
        async for result in session.subscribe(query):
            first_result = result
            break

    print("Client received:", first_result)
