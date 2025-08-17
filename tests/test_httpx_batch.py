from typing import Mapping

import pytest

from gql import Client, GraphQLRequest
from gql.transport.exceptions import (
    TransportClosed,
    TransportProtocolError,
    TransportQueryError,
)

# Marking all tests in this file with the httpx marker
pytestmark = pytest.mark.httpx

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
async def test_httpx_async_batch_query(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_list,
            content_type="application/json",
            headers={"dummy": "test1234"},
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:

        query = [GraphQLRequest(query1_str)]

        # Execute query asynchronously
        results = await session.execute_batch(query)

        result = results[0]

        continents = result["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"

        # Checking response headers are saved in the transport
        assert hasattr(transport, "response_headers")
        assert isinstance(transport.response_headers, Mapping)
        assert transport.response_headers["dummy"] == "test1234"


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_sync_batch_query(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_list,
            content_type="application/json",
            headers={"dummy": "test1234"},
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXTransport(url=url, timeout=10)

    def test_code():
        with Client(transport=transport) as session:

            query = [GraphQLRequest(query1_str)]

            results = session.execute_batch(query)

            result = results[0]

            continents = result["continents"]

            africa = continents[0]

            assert africa["code"] == "AF"

            # Checking response headers are saved in the transport
            assert hasattr(transport, "response_headers")
            assert isinstance(transport.response_headers, Mapping)
            assert transport.response_headers["dummy"] == "test1234"

    await run_sync_test(server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_async_batch_query_without_session(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_list,
            content_type="application/json",
            headers={"dummy": "test1234"},
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    def test_code():
        transport = HTTPXAsyncTransport(url=url, timeout=10)

        client = Client(transport=transport)

        query = [GraphQLRequest(query1_str)]

        results = client.execute_batch(query)

        result = results[0]

        continents = result["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"

        # Checking response headers are saved in the transport
        assert hasattr(transport, "response_headers")
        assert isinstance(transport.response_headers, Mapping)
        assert transport.response_headers["dummy"] == "test1234"

    await run_sync_test(server, test_code)


query1_server_error_answer_list = '[{"errors": ["Error 1", "Error 2"]}]'


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_async_batch_error_code(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(
            text=query1_server_error_answer_list, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url)

    async with Client(transport=transport) as session:

        query = [GraphQLRequest(query1_str)]

        with pytest.raises(TransportQueryError):
            await session.execute_batch(query)


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
async def test_httpx_async_batch_invalid_protocol(aiohttp_server, response):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(text=response, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:

        query = [GraphQLRequest(query1_str)]

        with pytest.raises(TransportProtocolError):
            await session.execute_batch(query)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_async_batch_cannot_execute_if_not_connected(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_list,
            content_type="application/json",
            headers={"dummy": "test1234"},
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url, timeout=10)

    query = [GraphQLRequest(query1_str)]

    with pytest.raises(TransportClosed):
        await transport.execute_batch(query)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_sync_batch_cannot_execute_if_not_connected(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_list,
            content_type="application/json",
            headers={"dummy": "test1234"},
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXTransport(url=url, timeout=10)

    query = [GraphQLRequest(query1_str)]

    with pytest.raises(TransportClosed):
        transport.execute_batch(query)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_async_batch_extra_args(aiohttp_server):
    import httpx
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_list,
            content_type="application/json",
            headers={"dummy": "test1234"},
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    # passing extra arguments to httpx.AsyncClient
    inner_transport = httpx.AsyncHTTPTransport(retries=2)
    transport = HTTPXAsyncTransport(url=url, max_redirects=2, transport=inner_transport)

    async with Client(transport=transport) as session:

        query = [GraphQLRequest(query1_str)]

        # Passing extra arguments to the post method
        results = await session.execute_batch(
            query, extra_args={"follow_redirects": True}
        )

        result = results[0]

        continents = result["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"


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
async def test_httpx_async_batch_query_with_extensions(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_with_extensions_list,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url)

    query = [GraphQLRequest(query1_str)]

    async with Client(transport=transport) as session:

        execution_results = await session.execute_batch(
            query, get_execution_result=True
        )

        assert execution_results[0].extensions["key1"] == "val1"


ONLINE_URL = "https://countries.trevorblades.workers.dev/graphql"


@pytest.mark.online
@pytest.mark.asyncio
async def test_httpx_batch_online_async_manual():

    from gql.transport.httpx import HTTPXAsyncTransport

    client = Client(
        transport=HTTPXAsyncTransport(url=ONLINE_URL),
    )

    query = """
        query getContinentName($continent_code: ID!) {
          continent(code: $continent_code) {
            name
          }
        }
    """

    async with client as session:

        request_eu = GraphQLRequest(query, variable_values={"continent_code": "EU"})
        request_af = GraphQLRequest(query, variable_values={"continent_code": "AF"})

        result_eu, result_af = await session.execute_batch([request_eu, request_af])

        assert result_eu["continent"]["name"] == "Europe"
        assert result_af["continent"]["name"] == "Africa"


@pytest.mark.online
@pytest.mark.asyncio
async def test_httpx_batch_online_sync_manual():

    from gql.transport.httpx import HTTPXTransport

    client = Client(
        transport=HTTPXTransport(url=ONLINE_URL),
    )

    query = """
        query getContinentName($continent_code: ID!) {
          continent(code: $continent_code) {
            name
          }
        }
    """

    with client as session:

        request_eu = GraphQLRequest(query, variable_values={"continent_code": "EU"})
        request_af = GraphQLRequest(query, variable_values={"continent_code": "AF"})

        result_eu, result_af = session.execute_batch([request_eu, request_af])

        assert result_eu["continent"]["name"] == "Europe"
        assert result_af["continent"]["name"] == "Africa"
