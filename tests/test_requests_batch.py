from typing import Mapping

import pytest

from gql import Client, gql
from gql.transport.data_structures.graphql_request import GraphQLRequest
from gql.transport.exceptions import (
    TransportClosed,
    TransportProtocolError,
    TransportQueryError,
    TransportServerError,
)

# Marking all tests in this file with the requests marker
pytestmark = pytest.mark.requests

query1_str = """
    query getContinents {
      continents {
        code
        name
      }
    }
"""

query1_server_answer_list = (
    '[{"data":{"continents":['
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
    '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
    '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
    '{"code":"SA","name":"South America"}]}}]'
)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_query(event_loop, aiohttp_server, run_sync_test):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_list,
            content_type="application/json",
            headers={"dummy": "test1234"},
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        transport = RequestsHTTPTransport(url=url)

        with Client(transport=transport) as session:

            query = [GraphQLRequest(document=gql(query1_str))]

            # Execute query synchronously
            results = session.execute_batch(query)

            continents = results[0]["continents"]

            africa = continents[0]

            assert africa["code"] == "AF"

            # Checking response headers are saved in the transport
            assert hasattr(transport, "response_headers")
            assert isinstance(transport.response_headers, Mapping)
            assert transport.response_headers["dummy"] == "test1234"

    await run_sync_test(event_loop, server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_cookies(event_loop, aiohttp_server, run_sync_test):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        assert "COOKIE" in request.headers
        assert "cookie1=val1" == request.headers["COOKIE"]

        return web.Response(
            text=query1_server_answer_list, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        transport = RequestsHTTPTransport(url=url, cookies={"cookie1": "val1"})

        with Client(transport=transport) as session:

            query = [GraphQLRequest(document=gql(query1_str))]

            # Execute query synchronously
            results = session.execute_batch(query)

            continents = results[0]["continents"]

            africa = continents[0]

            assert africa["code"] == "AF"

    await run_sync_test(event_loop, server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_error_code_401(event_loop, aiohttp_server, run_sync_test):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        # Will generate http error code 401
        return web.Response(
            text='{"error":"Unauthorized","message":"401 Client Error: Unauthorized"}',
            content_type="application/json",
            status=401,
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        transport = RequestsHTTPTransport(url=url)

        with Client(transport=transport) as session:

            query = [GraphQLRequest(document=gql(query1_str))]

            with pytest.raises(TransportServerError) as exc_info:
                session.execute_batch(query)

            assert "401 Client Error: Unauthorized" in str(exc_info.value)

    await run_sync_test(event_loop, server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_error_code_429(event_loop, aiohttp_server, run_sync_test):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        # Will generate http error code 429
        return web.Response(
            text="""
<html>
  <head>
     <title>Too Many Requests</title>
  </head>
  <body>
     <h1>Too Many Requests</h1>
     <p>I only allow 50 requests per hour to this Web site per
        logged in user.  Try again soon.</p>
  </body>
</html>""",
            content_type="text/html",
            status=429,
            headers={"Retry-After": "3600"},
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        transport = RequestsHTTPTransport(url=url)

        with Client(transport=transport) as session:

            query = [GraphQLRequest(document=gql(query1_str))]

            with pytest.raises(TransportServerError) as exc_info:
                session.execute_batch(query)

            assert "429, message='Too Many Requests'" in str(exc_info.value)

        # Checking response headers are saved in the transport
        assert hasattr(transport, "response_headers")
        assert isinstance(transport.response_headers, Mapping)
        assert transport.response_headers["Retry-After"] == "3600"


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_error_code_500(event_loop, aiohttp_server, run_sync_test):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        # Will generate http error code 500
        raise Exception("Server error")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        transport = RequestsHTTPTransport(url=url)

        with Client(transport=transport) as session:

            query = [GraphQLRequest(document=gql(query1_str))]

            with pytest.raises(TransportServerError):
                session.execute_batch(query)

    await run_sync_test(event_loop, server, test_code)


query1_server_error_answer_list = '[{"errors": ["Error 1", "Error 2"]}]'


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_error_code(event_loop, aiohttp_server, run_sync_test):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        return web.Response(
            text=query1_server_error_answer_list, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        transport = RequestsHTTPTransport(url=url)

        with Client(transport=transport) as session:

            query = [GraphQLRequest(document=gql(query1_str))]

            with pytest.raises(TransportQueryError):
                session.execute_batch(query)

    await run_sync_test(event_loop, server, test_code)


invalid_protocol_responses = [
    "{}",
    "qlsjfqsdlkj",
    '{"not_data_or_errors": 35}',
    "[{}]",
    "[qlsjfqsdlkj]",
    '[{"not_data_or_errors": 35}]',
    "[]",
    "[1]",
]


@pytest.mark.aiohttp
@pytest.mark.asyncio
@pytest.mark.parametrize("response", invalid_protocol_responses)
async def test_requests_invalid_protocol(
    event_loop, aiohttp_server, response, run_sync_test
):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        return web.Response(text=response, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        transport = RequestsHTTPTransport(url=url)

        with Client(transport=transport) as session:

            query = [GraphQLRequest(document=gql(query1_str))]

            with pytest.raises(TransportProtocolError):
                session.execute_batch(query)

    await run_sync_test(event_loop, server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_cannot_execute_if_not_connected(
    event_loop, aiohttp_server, run_sync_test
):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_list, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        transport = RequestsHTTPTransport(url=url)

        query = [GraphQLRequest(document=gql(query1_str))]

        with pytest.raises(TransportClosed):
            transport.execute_batch(query)

    await run_sync_test(event_loop, server, test_code)


query1_server_answer_with_extensions_list = (
    '[{"data":{"continents":['
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
    '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
    '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
    '{"code":"SA","name":"South America"}]},'
    '"extensions": {"key1": "val1"}'
    "}]"
)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_query_with_extensions(
    event_loop, aiohttp_server, run_sync_test
):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_with_extensions_list,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        transport = RequestsHTTPTransport(url=url)

        with Client(transport=transport) as session:

            query = [GraphQLRequest(document=gql(query1_str))]

            execution_results = session.execute_batch(query, get_execution_result=True)

            assert execution_results[0].extensions["key1"] == "val1"

    await run_sync_test(event_loop, server, test_code)
