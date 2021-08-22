import asyncio

import pytest

from gql import Client, gql
from gql.transport.exceptions import (
    TransportProtocolError,
    TransportQueryError,
    TransportServerError,
)

from .conftest import MS

# Marking all tests in this file with the websockets marker
pytestmark = pytest.mark.websockets


def ensure_list(s):
    return (
        s
        if s is None or isinstance(s, list)
        else list(s)
        if isinstance(s, tuple)
        else [s]
    )


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


# other protocol exceptions

reply_ref_null_answer = (
    '{"event":"phx_reply","payload":{}',
    '"ref":null,' '"topic":"test_topic"}',
)

reply_ref_zero_answer = (
    '{"event":"phx_reply","payload":{}',
    '"ref":0,' '"topic":"test_topic"}',
)


# "status":"error" responses

generic_error_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"status":"error"},'
    '"ref":2,'
    '"topic":"test_topic"}'
)

error_with_reason_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"response":{"reason":"internal error"},'
    '"status":"error"},'
    '"ref":2,'
    '"topic":"test_topic"}'
)

multiple_errors_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"response":{"errors": ["error 1", "error 2"]},'
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

invalid_payload_data_answer = (
    '{"event":"phx_reply",' '"payload":"INVALID",' '"ref":2,' '"topic":"test_topic"}'
)

# "status":"ok" exceptions

invalid_response_server_answer = (
    '{"event":"phx_reply",'
    '"payload":{"response":"INVALID",'
    '"status":"ok"}'
    '"ref":2,'
    '"topic":"test_topic"}'
)

invalid_response_keys_server_answer = (
    '{"event":"phx_reply",'
    '"payload":{"response":'
    '{"data":{"continents":null},"invalid":null}",'
    '"status":"ok"}'
    '"ref":2,'
    '"topic":"test_topic"}'
)

invalid_event_server_answer = '{"event":"unknown"}'


def query_server(server_answers=default_query_server_answer):
    from .conftest import PhoenixChannelServerHelper

    async def phoenix_server(ws, path):
        await PhoenixChannelServerHelper.send_connection_ack(ws)
        await ws.recv()
        for server_answer in ensure_list(server_answers):
            await ws.send(server_answer)
        await PhoenixChannelServerHelper.send_close(ws)
        await ws.wait_closed()

    return phoenix_server


async def no_connection_ack_phoenix_server(ws, path):
    from .conftest import PhoenixChannelServerHelper

    await ws.recv()
    await PhoenixChannelServerHelper.send_close(ws)
    await ws.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "server",
    [
        query_server(reply_ref_null_answer),
        query_server(reply_ref_zero_answer),
        query_server(invalid_payload_data_answer),
        query_server(invalid_response_server_answer),
        query_server(invalid_response_keys_server_answer),
        no_connection_ack_phoenix_server,
        query_server(invalid_event_server_answer),
    ],
    indirect=True,
)
@pytest.mark.parametrize("query_str", [query1_str])
async def test_phoenix_channel_query_protocol_error(event_loop, server, query_str):

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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "server",
    [
        query_server(generic_error_server_answer),
        query_server(error_with_reason_server_answer),
        query_server(multiple_errors_server_answer),
        query_server(timeout_server_answer),
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


query2_str = """
    subscription getContinents {
      continents {
        code
        name
      }
    }
"""

default_subscription_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"response":{"subscriptionId":"test_subscription"},'
    '"status":"ok"},'
    '"ref":2,'
    '"topic":"test_topic"}'
)

ref_is_not_an_integer_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"response":{"subscriptionId":"test_subscription"},'
    '"status":"ok"},'
    '"ref":"not_an_integer",'
    '"topic":"test_topic"}'
)

missing_ref_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"response":{"subscriptionId":"test_subscription"},'
    '"status":"ok"},'
    '"topic":"test_topic"}'
)

missing_subscription_id_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"response":{},"status":"ok"},'
    '"ref":2,'
    '"topic":"test_topic"}'
)

null_subscription_id_server_answer = (
    '{"event":"phx_reply",'
    '"payload":'
    '{"response":{"subscriptionId":null},"status":"ok"},'
    '"ref":2,'
    '"topic":"test_topic"}'
)

default_subscription_data_answer = (
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

default_subscription_unsubscribe_answer = (
    '{"event":"phx_reply",'
    '"payload":{"response":{"subscriptionId":"test_subscription"},'
    '"status":"ok"},'
    '"ref":3,'
    '"topic":"test_topic"}'
)

missing_subscription_id_data_answer = (
    '{"event":"subscription:data","payload":'
    '{"result":'
    '{"data":{"continents":['
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
    '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
    '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
    '{"code":"SA","name":"South America"}]}}},'
    '"ref":null,'
    '"topic":"test_subscription"}'
)

null_subscription_id_data_answer = (
    '{"event":"subscription:data","payload":'
    '{"subscriptionId":null,"result":'
    '{"data":{"continents":['
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
    '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
    '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
    '{"code":"SA","name":"South America"}]}}},'
    '"ref":null,'
    '"topic":"test_subscription"}'
)

invalid_subscription_id_data_answer = (
    '{"event":"subscription:data","payload":'
    '{"subscriptionId":"INVALID","result":'
    '{"data":{"continents":['
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
    '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
    '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
    '{"code":"SA","name":"South America"}]}}},'
    '"ref":null,'
    '"topic":"test_subscription"}'
)

invalid_payload_data_answer = (
    '{"event":"subscription:data",'
    '"payload":"INVALID",'
    '"ref":null,'
    '"topic":"test_subscription"}'
)

invalid_result_data_answer = (
    '{"event":"subscription:data","payload":'
    '{"subscriptionId":"test_subscription","result":"INVALID"},'
    '"ref":null,'
    '"topic":"test_subscription"}'
)

invalid_result_keys_data_answer = (
    '{"event":"subscription:data",'
    '"payload":{"subscriptionId":"test_subscription",'
    '"result":{"data":{"continents":null},"invalid":null}},'
    '"ref":null,'
    '"topic":"test_subscription"}'
)

invalid_subscription_ref_answer = (
    '{"event":"phx_reply",'
    '"payload":{"response":{"subscriptionId":"test_subscription"},'
    '"status":"ok"},'
    '"ref":99,'
    '"topic":"test_topic"}'
)

mismatched_unsubscribe_answer = (
    '{"event":"phx_reply",'
    '"payload":{"response":{"subscriptionId":"no_such_subscription"},'
    '"status":"ok"},'
    '"ref":3,'
    '"topic":"test_topic"}'
)


def subscription_server(
    server_answers=default_subscription_server_answer,
    data_answers=default_subscription_data_answer,
    unsubscribe_answers=default_subscription_unsubscribe_answer,
):
    from .conftest import PhoenixChannelServerHelper
    import json

    async def phoenix_server(ws, path):
        await PhoenixChannelServerHelper.send_connection_ack(ws)
        await ws.recv()
        if server_answers is not None:
            for server_answer in ensure_list(server_answers):
                await ws.send(server_answer)
        if data_answers is not None:
            for data_answer in ensure_list(data_answers):
                await ws.send(data_answer)
        if unsubscribe_answers is not None:
            result = await ws.recv()
            json_result = json.loads(result)
            assert json_result["event"] == "unsubscribe"
            for unsubscribe_answer in ensure_list(unsubscribe_answers):
                await ws.send(unsubscribe_answer)
        else:
            await PhoenixChannelServerHelper.send_close(ws)
        await ws.wait_closed()

    return phoenix_server


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "server",
    [
        subscription_server(invalid_subscription_ref_answer),
        subscription_server(missing_subscription_id_server_answer),
        subscription_server(null_subscription_id_server_answer),
        subscription_server(
            [default_subscription_server_answer, default_subscription_server_answer]
        ),
        subscription_server(data_answers=missing_subscription_id_data_answer),
        subscription_server(data_answers=null_subscription_id_data_answer),
        subscription_server(data_answers=invalid_subscription_id_data_answer),
        subscription_server(data_answers=ref_is_not_an_integer_server_answer),
        subscription_server(data_answers=missing_ref_server_answer),
        subscription_server(data_answers=invalid_payload_data_answer),
        subscription_server(data_answers=invalid_result_data_answer),
        subscription_server(data_answers=invalid_result_keys_data_answer),
    ],
    indirect=True,
)
@pytest.mark.parametrize("query_str", [query2_str])
async def test_phoenix_channel_subscription_protocol_error(
    event_loop, server, query_str
):

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
            async for _result in session.subscribe(query):
                await asyncio.sleep(10 * MS)
                break


server_error_server_answer = '{"event":"phx_error", "ref":2, "topic":"test_topic"}'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "server", [query_server(server_error_server_answer)], indirect=True,
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


# These cannot be caught by the client
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "server",
    [
        subscription_server(unsubscribe_answers=invalid_subscription_ref_answer),
        subscription_server(unsubscribe_answers=mismatched_unsubscribe_answer),
    ],
    indirect=True,
)
@pytest.mark.parametrize("query_str", [query2_str])
async def test_phoenix_channel_unsubscribe_error(event_loop, server, query_str):

    from gql.transport.phoenix_channel_websockets import (
        PhoenixChannelWebsocketsTransport,
    )

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"

    # Reduce close_timeout. These tests will wait for an unsubscribe
    # reply that will never come...
    sample_transport = PhoenixChannelWebsocketsTransport(
        channel_name="test_channel", url=url, close_timeout=1
    )

    query = gql(query_str)
    async with Client(transport=sample_transport) as session:
        async for _result in session.subscribe(query):
            break


# We can force the error if somehow the generator is still running while
# we receive a mismatched unsubscribe answer
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "server",
    [subscription_server(unsubscribe_answers=mismatched_unsubscribe_answer)],
    indirect=True,
)
@pytest.mark.parametrize("query_str", [query2_str])
async def test_phoenix_channel_unsubscribe_error_forcing(event_loop, server, query_str):

    from gql.transport.phoenix_channel_websockets import (
        PhoenixChannelWebsocketsTransport,
    )

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"

    sample_transport = PhoenixChannelWebsocketsTransport(
        channel_name="test_channel", url=url, close_timeout=1
    )

    query = gql(query_str)
    with pytest.raises(TransportProtocolError):
        async with Client(transport=sample_transport) as session:
            async for _result in session.subscribe(query):
                await session.transport._send_stop_message(2)
                await asyncio.sleep(10 * MS)
