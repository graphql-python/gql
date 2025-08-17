import asyncio
from typing import Mapping

import pytest

from gql import Client, GraphQLRequest, gql
from gql.transport.exceptions import (
    TransportClosed,
    TransportProtocolError,
    TransportQueryError,
    TransportServerError,
)

# Marking all tests in this file with the aiohttp marker
pytestmark = pytest.mark.aiohttp

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

query1_server_answer_twice_list = (
    "["
    '{"data":{"continents":['
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
    '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
    '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
    '{"code":"SA","name":"South America"}]}},'
    '{"data":{"continents":['
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
    '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
    '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
    '{"code":"SA","name":"South America"}]}}'
    "]"
)


@pytest.mark.asyncio
async def test_aiohttp_batch_query(aiohttp_server):
    from aiohttp import web

    from gql.transport.aiohttp import AIOHTTPTransport

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

    transport = AIOHTTPTransport(url=url, timeout=10)

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


@pytest.mark.asyncio
async def test_aiohttp_batch_query_auto_batch_enabled(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.aiohttp import AIOHTTPTransport

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

    transport = AIOHTTPTransport(url=url, timeout=10)

    async with Client(
        transport=transport,
        batch_interval=0.01,  # 10ms batch interval
    ) as session:

        query = gql(query1_str)

        result = await session.execute(query)

        continents = result["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"

        # Checking response headers are saved in the transport
        assert hasattr(transport, "response_headers")
        assert isinstance(transport.response_headers, Mapping)
        assert transport.response_headers["dummy"] == "test1234"


@pytest.mark.asyncio
async def test_aiohttp_batch_auto_two_requests(aiohttp_server):
    from aiohttp import web

    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_twice_list,
            content_type="application/json",
            headers={"dummy": "test1234"},
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = AIOHTTPTransport(url=url, timeout=10)

    async with Client(
        transport=transport,
        batch_interval=0.01,
    ) as session:

        async def test_coroutine():
            query = gql(query1_str)

            # Execute query asynchronously
            result = await session.execute(query)

            continents = result["continents"]

            africa = continents[0]

            assert africa["code"] == "AF"

        # Create two concurrent tasks that will be batched together
        tasks = []
        for _ in range(2):
            task = asyncio.create_task(test_coroutine())
            tasks.append(task)

        # Wait for all tasks to complete
        await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_aiohttp_batch_auto_two_requests_close_session_directly(aiohttp_server):
    from aiohttp import web

    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_twice_list,
            content_type="application/json",
            headers={"dummy": "test1234"},
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = AIOHTTPTransport(url=url, timeout=10)

    async with Client(
        transport=transport,
        batch_interval=0.1,
    ) as session:

        async def test_coroutine():
            query = gql(query1_str)

            # Execute query asynchronously
            result = await session.execute(query)

            continents = result["continents"]

            africa = continents[0]

            assert africa["code"] == "AF"

        # Create two concurrent tasks that will be batched together
        tasks = []
        for _ in range(2):
            task = asyncio.create_task(test_coroutine())
            tasks.append(task)

        await asyncio.sleep(0.01)

    # Wait for all tasks to complete
    await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_aiohttp_batch_error_code_401(aiohttp_server):
    from aiohttp import web

    from gql.transport.aiohttp import AIOHTTPTransport

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

    transport = AIOHTTPTransport(url=url, timeout=10)

    async with Client(
        transport=transport,
        batch_interval=0.01,  # 10ms batch interval
    ) as session:

        query = gql(query1_str)

        with pytest.raises(TransportServerError) as exc_info:
            await session.execute(query)

        assert "401, message='Unauthorized'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_aiohttp_batch_query_without_session(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.aiohttp import AIOHTTPTransport

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
        transport = AIOHTTPTransport(url=url, timeout=10)

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


@pytest.mark.asyncio
async def test_aiohttp_batch_error_code(aiohttp_server):
    from aiohttp import web

    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        return web.Response(
            text=query1_server_error_answer_list, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    transport = AIOHTTPTransport(url=url)

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


@pytest.mark.asyncio
@pytest.mark.parametrize("response", invalid_protocol_responses)
async def test_aiohttp_batch_invalid_protocol(aiohttp_server, response):
    from aiohttp import web

    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        return web.Response(text=response, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    transport = AIOHTTPTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:

        query = [GraphQLRequest(query1_str)]

        with pytest.raises(TransportProtocolError):
            await session.execute_batch(query)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_aiohttp_batch_cannot_execute_if_not_connected(
    aiohttp_server, run_sync_test
):
    from aiohttp import web

    from gql.transport.aiohttp import AIOHTTPTransport

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

    transport = AIOHTTPTransport(url=url, timeout=10)

    query = [GraphQLRequest(query1_str)]

    with pytest.raises(TransportClosed):
        await transport.execute_batch(query)


@pytest.mark.asyncio
async def test_aiohttp_batch_extra_args(aiohttp_server):
    from aiohttp import web

    from gql.transport.aiohttp import AIOHTTPTransport

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

    # passing extra arguments to aiohttp.ClientSession
    from aiohttp import DummyCookieJar

    jar = DummyCookieJar()
    transport = AIOHTTPTransport(
        url=url, timeout=10, client_session_args={"version": "1.1", "cookie_jar": jar}
    )

    async with Client(transport=transport) as session:

        query = [GraphQLRequest(query1_str)]

        # Passing extra arguments to the post method of aiohttp
        results = await session.execute_batch(
            query, extra_args={"allow_redirects": False}
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


@pytest.mark.asyncio
async def test_aiohttp_batch_query_with_extensions(aiohttp_server):
    from aiohttp import web

    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_with_extensions_list,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    transport = AIOHTTPTransport(url=url)

    query = [GraphQLRequest(query1_str)]

    async with Client(transport=transport) as session:

        execution_results = await session.execute_batch(
            query, get_execution_result=True
        )

        assert execution_results[0].extensions["key1"] == "val1"


ONLINE_URL = "https://countries.trevorblades.workers.dev/graphql"


@pytest.mark.online
@pytest.mark.asyncio
async def test_aiohttp_batch_online_manual():

    from gql.transport.aiohttp import AIOHTTPTransport

    client = Client(
        transport=AIOHTTPTransport(url=ONLINE_URL, timeout=10),
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
