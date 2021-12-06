import asyncio
import json
from base64 import b64decode
from typing import List
from urllib import parse

import pytest

from gql import Client, gql

from .conftest import MS, WebSocketServerHelper

# Marking all tests in this file with the websockets marker
pytestmark = pytest.mark.websockets

SEND_MESSAGE_DELAY = 20 * MS
NB_MESSAGES = 10

DUMMY_API_KEY = "da2-thisisadummyapikey01234567"
DUMMY_ACCESS_KEY_ID = "DUMMYACCESSKEYID0123"
DUMMY_ACCESS_KEY_ID_NOT_ALLOWED = "DUMMYACCESSKEYID!ALL"
DUMMY_ACCESS_KEY_IDS = [DUMMY_ACCESS_KEY_ID, DUMMY_ACCESS_KEY_ID_NOT_ALLOWED]
DUMMY_SECRET_ACCESS_KEY = "ThisIsADummySecret0123401234012340123401"
DUMMY_SECRET_SESSION_TOKEN = (
    "FwoREDACTEDzEREDACTED+YREDACTEDJLREDACTEDz2REDACTEDH5RE"
    "DACTEDbVREDACTEDqwREDACTEDHJREDACTEDxFREDACTEDtMREDACTED5kREDACTEDSwREDACTED0BRED"
    "ACTEDuDREDACTEDm4REDACTEDSBREDACTEDaoREDACTEDP2REDACTEDCBREDACTED0wREDACTEDmdREDA"
    "CTEDyhREDACTEDSKREDACTEDYbREDACTEDfeREDACTED3UREDACTEDaKREDACTEDi1REDACTEDGEREDAC"
    "TED4VREDACTEDjmREDACTEDYcREDACTEDkQREDACTEDyI="
)
REGION_NAME = "eu-west-3"

# List which can used to store received messages by the server
logged_messages: List[str] = []


def realtime_appsync_server_factory(
    keepalive=False, not_json_answer=False, error_without_id=False
):
    def verify_headers(headers, in_query=False):
        """Returns an error or None if all is ok"""

        if "x-api-key" in headers:
            print("API KEY Authentication detected!")

            if headers["x-api-key"] == DUMMY_API_KEY:
                return None

        elif "Authorization" in headers:
            if "X-Amz-Security-Token" in headers:
                with_token = True
                print("IAM Authentication with token detected!")
            else:
                with_token = False
                print("IAM Authentication with token detected!")
                print("IAM Authentication without token detected!")

            assert headers["accept"] == "application/json, text/javascript"
            assert headers["content-encoding"] == "amz-1.0"
            assert headers["content-type"] == "application/json; charset=UTF-8"
            assert "X-Amz-Date" in headers

            authorization_fields = headers["Authorization"].split(" ")

            assert authorization_fields[0] == "AWS4-HMAC-SHA256"

            credential_field = authorization_fields[1][:-1].split("=")
            assert credential_field[0] == "Credential"
            credential_content = credential_field[1].split("/")
            assert credential_content[0] in DUMMY_ACCESS_KEY_IDS

            if in_query:
                if credential_content[0] == DUMMY_ACCESS_KEY_ID_NOT_ALLOWED:
                    return {
                        "errorType": "UnauthorizedException",
                        "message": "Permission denied",
                    }

            # assert credential_content[1]== date
            # assert credential_content[2]== region
            assert credential_content[3] == "appsync"
            assert credential_content[4] == "aws4_request"

            signed_headers_field = authorization_fields[2][:-1].split("=")

            assert signed_headers_field[0] == "SignedHeaders"
            signed_headers = signed_headers_field[1].split(";")

            assert "accept" in signed_headers
            assert "content-encoding" in signed_headers
            assert "content-type" in signed_headers
            assert "host" in signed_headers
            assert "x-amz-date" in signed_headers

            if with_token:
                assert "x-amz-security-token" in signed_headers

            signature_field = authorization_fields[3].split("=")

            assert signature_field[0] == "Signature"

            return None

        return {
            "errorType": "com.amazonaws.deepdish.graphql.auth#UnauthorizedException",
            "message": "You are not authorized to make this call.",
            "errorCode": 400,
        }

    async def realtime_appsync_server_template(ws, path):
        import websockets

        logged_messages.clear()

        try:
            if not_json_answer:
                await ws.send("Something not json")
                return

            if error_without_id:
                await ws.send(
                    json.dumps(
                        {
                            "type": "error",
                            "payload": {
                                "errors": [
                                    {
                                        "errorType": "Error without id",
                                        "message": (
                                            "Sometimes AppSync will send you "
                                            "an error without an id"
                                        ),
                                    }
                                ]
                            },
                        },
                        separators=(",", ":"),
                    )
                )
                return

            print(f"path = {path}")

            path_base, parameters_str = path.split("?")

            assert path_base == "/graphql"

            parameters = parse.parse_qs(parameters_str)

            header_param = parameters["header"][0]
            payload_param = parameters["payload"][0]

            assert payload_param == "e30="

            headers = json.loads(b64decode(header_param).decode())

            print("\nHeaders received in URL:")
            for key, value in headers.items():
                print(f"    {key}: {value}")
            print("\n")

            error = verify_headers(headers)

            if error is not None:
                await ws.send(
                    json.dumps(
                        {"payload": {"errors": [error]}, "type": "connection_error"},
                        separators=(",", ":"),
                    )
                )
                return

            await WebSocketServerHelper.send_connection_ack(
                ws, payload='{"connectionTimeoutMs":300000}'
            )

            result = await ws.recv()
            logged_messages.append(result)

            json_result = json.loads(result)

            query_id = json_result["id"]
            assert json_result["type"] == "start"

            payload = json_result["payload"]

            # With appsync, the data field is serialized to string
            data_str = payload["data"]
            extensions = payload["extensions"]

            data = json.loads(data_str)

            query = data["query"]
            variables = data.get("variables", None)
            operation_name = data.get("operationName", None)
            print(f"Received query: {query}")
            print(f"Received variables: {variables}")
            print(f"Received operation_name: {operation_name}")

            authorization = extensions["authorization"]
            print("\nHeaders received in the extensions of the query:")
            for key, value in authorization.items():
                print(f"    {key}: {value}")
            print("\n")

            error = verify_headers(headers, in_query=True)

            if error is not None:
                await ws.send(
                    json.dumps(
                        {
                            "id": str(query_id),
                            "type": "error",
                            "payload": {"errors": [error]},
                        },
                        separators=(",", ":"),
                    )
                )
                return

            await ws.send(
                json.dumps(
                    {"id": str(query_id), "type": "start_ack"}, separators=(",", ":")
                )
            )

            async def send_message_coro():
                print("            Server: send message task started")
                try:
                    for number in range(NB_MESSAGES):
                        payload = {
                            "data": {
                                "onCreateMessage": {"message": f"Hello world {number}!"}
                            }
                        }

                        if operation_name or variables:

                            payload["extensions"] = {}

                            if operation_name:
                                payload["extensions"]["operation_name"] = operation_name
                            if variables:
                                payload["extensions"]["variables"] = variables

                        await ws.send(
                            json.dumps(
                                {
                                    "id": str(query_id),
                                    "type": "data",
                                    "payload": payload,
                                },
                                separators=(",", ":"),
                            )
                        )
                        await asyncio.sleep(SEND_MESSAGE_DELAY)
                finally:
                    print("            Server: send message task ended")

            print("            Server: starting send message task")
            send_message_task = asyncio.ensure_future(send_message_coro())

            async def keepalive_coro():
                while True:
                    await asyncio.sleep(5 * MS)
                    try:
                        await WebSocketServerHelper.send_keepalive(ws)
                    except websockets.exceptions.ConnectionClosed:
                        break

            if keepalive:
                print("            Server: starting keepalive task")
                keepalive_task = asyncio.ensure_future(keepalive_coro())

            async def receiving_coro():
                print("            Server: receiving task started")
                try:
                    nonlocal send_message_task
                    while True:

                        try:
                            result = await ws.recv()
                            logged_messages.append(result)
                        except websockets.exceptions.ConnectionClosed:
                            break

                finally:
                    print("            Server: receiving task ended")
                    if keepalive:
                        keepalive_task.cancel()

            print("            Server: starting receiving task")
            receiving_task = asyncio.ensure_future(receiving_coro())

            try:
                print(
                    "            Server: waiting for sending message task to complete"
                )
                await send_message_task
            except asyncio.CancelledError:
                print("            Server: Now sending message task is cancelled")

            print("            Server: sending complete message")
            await WebSocketServerHelper.send_complete(ws, query_id)

            if keepalive:
                print("            Server: cancelling keepalive task")
                keepalive_task.cancel()
                try:
                    await keepalive_task
                except asyncio.CancelledError:
                    print("            Server: Now keepalive task is cancelled")

            print("            Server: waiting for client to close the connection")
            try:
                await asyncio.wait_for(receiving_task, 1000 * MS)
            except asyncio.TimeoutError:
                pass

            print("            Server: cancelling receiving task")
            receiving_task.cancel()

            try:
                await receiving_task
            except asyncio.CancelledError:
                print("            Server: Now receiving task is cancelled")

        except websockets.exceptions.ConnectionClosedOK:
            pass
        except AssertionError as e:
            print(f"\n            Server: Assertion failed: {e!s}\n")
        except Exception as e:
            print(f"\n            Server: Exception received: {e!s}\n")
        finally:
            print("            Server: waiting for websocket connection to close")
            await ws.wait_closed()
            print("            Server: connection closed")

    return realtime_appsync_server_template


async def realtime_appsync_server(ws, path):

    server = realtime_appsync_server_factory()
    await server(ws, path)


async def realtime_appsync_server_keepalive(ws, path):

    server = realtime_appsync_server_factory(keepalive=True)
    await server(ws, path)


async def realtime_appsync_server_not_json_answer(ws, path):

    server = realtime_appsync_server_factory(not_json_answer=True)
    await server(ws, path)


async def realtime_appsync_server_error_without_id(ws, path):

    server = realtime_appsync_server_factory(error_without_id=True)
    await server(ws, path)


on_create_message_subscription_str = """
subscription onCreateMessage {
  onCreateMessage {
    message
  }
}
"""


async def default_transport_test(transport):
    client = Client(transport=transport)

    expected_messages = [f"Hello world {number}!" for number in range(NB_MESSAGES)]
    received_messages = []

    async with client as session:
        subscription = gql(on_create_message_subscription_str)

        async for result in session.subscribe(subscription):

            message = result["onCreateMessage"]["message"]
            print(f"Message received: '{message}'")

            received_messages.append(message)

    assert expected_messages == received_messages


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [realtime_appsync_server_keepalive], indirect=True)
async def test_appsync_subscription_api_key(event_loop, server):

    from gql.transport.appsync_auth import AppSyncApiKeyAuthentication
    from gql.transport.appsync_websockets import AppSyncWebsocketsTransport

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"

    auth = AppSyncApiKeyAuthentication(host=server.hostname, api_key=DUMMY_API_KEY)

    transport = AppSyncWebsocketsTransport(
        url=url, auth=auth, keep_alive_timeout=(5 * SEND_MESSAGE_DELAY)
    )

    await default_transport_test(transport)


@pytest.mark.asyncio
@pytest.mark.botocore
@pytest.mark.parametrize("server", [realtime_appsync_server], indirect=True)
async def test_appsync_subscription_iam_with_token(event_loop, server):

    from gql.transport.appsync_auth import AppSyncIAMAuthentication
    from gql.transport.appsync_websockets import AppSyncWebsocketsTransport
    from botocore.credentials import Credentials

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"

    dummy_credentials = Credentials(
        access_key=DUMMY_ACCESS_KEY_ID,
        secret_key=DUMMY_SECRET_ACCESS_KEY,
        token=DUMMY_SECRET_SESSION_TOKEN,
    )

    auth = AppSyncIAMAuthentication(
        host=server.hostname, credentials=dummy_credentials, region_name=REGION_NAME
    )

    transport = AppSyncWebsocketsTransport(url=url, auth=auth)

    await default_transport_test(transport)


@pytest.mark.asyncio
@pytest.mark.botocore
@pytest.mark.parametrize("server", [realtime_appsync_server], indirect=True)
async def test_appsync_subscription_iam_without_token(event_loop, server):

    from gql.transport.appsync_auth import AppSyncIAMAuthentication
    from gql.transport.appsync_websockets import AppSyncWebsocketsTransport
    from botocore.credentials import Credentials

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"

    dummy_credentials = Credentials(
        access_key=DUMMY_ACCESS_KEY_ID, secret_key=DUMMY_SECRET_ACCESS_KEY,
    )

    auth = AppSyncIAMAuthentication(
        host=server.hostname, credentials=dummy_credentials, region_name=REGION_NAME
    )

    transport = AppSyncWebsocketsTransport(url=url, auth=auth)

    await default_transport_test(transport)


@pytest.mark.asyncio
@pytest.mark.botocore
@pytest.mark.parametrize("server", [realtime_appsync_server], indirect=True)
async def test_appsync_execute_method_not_allowed(event_loop, server):

    from gql.transport.appsync_auth import AppSyncIAMAuthentication
    from gql.transport.appsync_websockets import AppSyncWebsocketsTransport
    from botocore.credentials import Credentials

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"

    dummy_credentials = Credentials(
        access_key=DUMMY_ACCESS_KEY_ID, secret_key=DUMMY_SECRET_ACCESS_KEY,
    )

    auth = AppSyncIAMAuthentication(
        host=server.hostname, credentials=dummy_credentials, region_name=REGION_NAME
    )

    transport = AppSyncWebsocketsTransport(url=url, auth=auth)

    client = Client(transport=transport)

    async with client as session:
        query = gql(
            """
mutation createMessage($message: String!) {
  createMessage(input: {message: $message}) {
    id
    message
    createdAt
  }
}"""
        )

        variable_values = {"message": "Hello world!"}

        with pytest.raises(AssertionError) as exc_info:
            await session.execute(query, variable_values=variable_values)

        assert (
            "execute method is not allowed for AppSyncWebsocketsTransport "
            "because only subscriptions are allowed on the realtime endpoint."
        ) in str(exc_info)


@pytest.mark.asyncio
@pytest.mark.botocore
async def test_appsync_fetch_schema_from_transport_not_allowed(event_loop):

    from gql.transport.appsync_auth import AppSyncIAMAuthentication
    from gql.transport.appsync_websockets import AppSyncWebsocketsTransport
    from botocore.credentials import Credentials

    dummy_credentials = Credentials(
        access_key=DUMMY_ACCESS_KEY_ID, secret_key=DUMMY_SECRET_ACCESS_KEY,
    )

    auth = AppSyncIAMAuthentication(
        host="something", credentials=dummy_credentials, region_name=REGION_NAME
    )

    transport = AppSyncWebsocketsTransport(url="https://something", auth=auth)

    with pytest.raises(AssertionError) as exc_info:
        Client(transport=transport, fetch_schema_from_transport=True)

    assert (
        "fetch_schema_from_transport=True is not allowed for AppSyncWebsocketsTransport"
        " because only subscriptions are allowed on the realtime endpoint."
    ) in str(exc_info)


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [realtime_appsync_server], indirect=True)
async def test_appsync_subscription_api_key_unauthorized(event_loop, server):

    from gql.transport.appsync_auth import AppSyncApiKeyAuthentication
    from gql.transport.appsync_websockets import AppSyncWebsocketsTransport
    from gql.transport.exceptions import TransportServerError

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"

    auth = AppSyncApiKeyAuthentication(host=server.hostname, api_key="invalid")

    transport = AppSyncWebsocketsTransport(url=url, auth=auth)

    client = Client(transport=transport)

    with pytest.raises(TransportServerError) as exc_info:
        async with client as _:
            pass

    assert "You are not authorized to make this call." in str(exc_info)


@pytest.mark.asyncio
@pytest.mark.botocore
@pytest.mark.parametrize("server", [realtime_appsync_server], indirect=True)
async def test_appsync_subscription_iam_not_allowed(event_loop, server):

    from gql.transport.appsync_auth import AppSyncIAMAuthentication
    from gql.transport.appsync_websockets import AppSyncWebsocketsTransport
    from gql.transport.exceptions import TransportQueryError
    from botocore.credentials import Credentials

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"

    dummy_credentials = Credentials(
        access_key=DUMMY_ACCESS_KEY_ID_NOT_ALLOWED,
        secret_key=DUMMY_SECRET_ACCESS_KEY,
        token=DUMMY_SECRET_SESSION_TOKEN,
    )

    auth = AppSyncIAMAuthentication(
        host=server.hostname, credentials=dummy_credentials, region_name=REGION_NAME
    )

    transport = AppSyncWebsocketsTransport(url=url, auth=auth)

    client = Client(transport=transport)

    async with client as session:
        subscription = gql(on_create_message_subscription_str)

        with pytest.raises(TransportQueryError) as exc_info:

            async for result in session.subscribe(subscription):
                pass

        assert "Permission denied" in str(exc_info)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "server", [realtime_appsync_server_not_json_answer], indirect=True
)
async def test_appsync_subscription_server_sending_a_not_json_answer(
    event_loop, server
):

    from gql.transport.appsync_auth import AppSyncApiKeyAuthentication
    from gql.transport.appsync_websockets import AppSyncWebsocketsTransport
    from gql.transport.exceptions import TransportProtocolError

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"

    auth = AppSyncApiKeyAuthentication(host=server.hostname, api_key=DUMMY_API_KEY)

    transport = AppSyncWebsocketsTransport(url=url, auth=auth)

    client = Client(transport=transport)

    with pytest.raises(TransportProtocolError) as exc_info:
        async with client as _:
            pass

    assert "Server did not return a GraphQL result: Something not json" in str(exc_info)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "server", [realtime_appsync_server_error_without_id], indirect=True
)
async def test_appsync_subscription_server_sending_an_error_without_an_id(
    event_loop, server
):

    from gql.transport.appsync_auth import AppSyncApiKeyAuthentication
    from gql.transport.appsync_websockets import AppSyncWebsocketsTransport
    from gql.transport.exceptions import TransportServerError

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"

    auth = AppSyncApiKeyAuthentication(host=server.hostname, api_key=DUMMY_API_KEY)

    transport = AppSyncWebsocketsTransport(url=url, auth=auth)

    client = Client(transport=transport)

    with pytest.raises(TransportServerError) as exc_info:
        async with client as _:
            pass

    assert "Sometimes AppSync will send you an error without an id" in str(exc_info)


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [realtime_appsync_server_keepalive], indirect=True)
async def test_appsync_subscription_variable_values_and_operation_name(
    event_loop, server
):

    from gql.transport.appsync_auth import AppSyncApiKeyAuthentication
    from gql.transport.appsync_websockets import AppSyncWebsocketsTransport

    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"

    auth = AppSyncApiKeyAuthentication(host=server.hostname, api_key=DUMMY_API_KEY)

    transport = AppSyncWebsocketsTransport(
        url=url, auth=auth, keep_alive_timeout=(5 * SEND_MESSAGE_DELAY)
    )

    client = Client(transport=transport)

    expected_messages = [f"Hello world {number}!" for number in range(NB_MESSAGES)]
    received_messages = []

    async with client as session:
        subscription = gql(on_create_message_subscription_str)

        async for execution_result in session.subscribe(
            subscription,
            operation_name="onCreateMessage",
            variable_values={"key1": "val1"},
            get_execution_result=True,
        ):

            result = execution_result.data
            message = result["onCreateMessage"]["message"]
            print(f"Message received: '{message}'")

            received_messages.append(message)

            print(f"extensions received: {execution_result.extensions}")

            assert execution_result.extensions["operation_name"] == "onCreateMessage"
            variables = execution_result.extensions["variables"]
            assert variables["key1"] == "val1"

    assert expected_messages == received_messages
