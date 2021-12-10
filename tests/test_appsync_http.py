import json

import pytest

from gql import Client, gql


@pytest.mark.asyncio
@pytest.mark.aiohttp
@pytest.mark.botocore
async def test_appsync_iam_mutation(
    event_loop, aiohttp_server, fake_credentials_factory
):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport
    from gql.transport.appsync_auth import AppSyncIAMAuthentication
    from urllib.parse import urlparse

    async def handler(request):
        data = {
            "createMessage": {
                "id": "4b436192-aab2-460c-8bdf-4f2605eb63da",
                "message": "Hello world!",
                "createdAt": "2021-12-06T14:49:55.087Z",
            }
        }
        payload = {
            "data": data,
            "extensions": {"received_headers": dict(request.headers)},
        }

        return web.Response(
            text=json.dumps(payload, separators=(",", ":")),
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    # Extract host from url
    host = str(urlparse(url).netloc)

    auth = AppSyncIAMAuthentication(
        host=host, credentials=fake_credentials_factory(), region_name="us-east-1",
    )

    sample_transport = AIOHTTPTransport(url=url, auth=auth)

    async with Client(transport=sample_transport) as session:

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

        # Execute query asynchronously
        execution_result = await session.execute(query, get_execution_result=True)

        result = execution_result.data
        message = result["createMessage"]["message"]

        assert message == "Hello world!"

        sent_headers = execution_result.extensions["received_headers"]

        assert sent_headers["X-Amz-Security-Token"] == "fake-token"
        assert sent_headers["Authorization"].startswith(
            "AWS4-HMAC-SHA256 Credential=fake-access-key/"
        )
