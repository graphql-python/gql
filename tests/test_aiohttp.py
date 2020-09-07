import pytest
from aiohttp import DummyCookieJar, web

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import (
    TransportAlreadyConnected,
    TransportClosed,
    TransportProtocolError,
    TransportQueryError,
    TransportServerError,
)

query1_str = """
    query getContinents {
      continents {
        code
        name
      }
    }
"""

query1_server_answer = (
    '{"data":{"continents":['
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
    '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
    '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
    '{"code":"SA","name":"South America"}]}}'
)


@pytest.mark.asyncio
async def test_aiohttp_query(event_loop, aiohttp_server):
    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url, timeout=10)

    async with Client(transport=sample_transport,) as session:

        query = gql(query1_str)

        # Execute query asynchronously
        result = await session.execute(query)

        continents = result["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"


@pytest.mark.asyncio
async def test_aiohttp_error_code_500(event_loop, aiohttp_server):
    async def handler(request):
        # Will generate http error code 500
        raise Exception("Server error")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url)

    async with Client(transport=sample_transport,) as session:

        query = gql(query1_str)

        with pytest.raises(TransportServerError):
            await session.execute(query)


query1_server_error_answer = '{"errors": ["Error 1", "Error 2"]}'


@pytest.mark.asyncio
async def test_aiohttp_error_code(event_loop, aiohttp_server):
    async def handler(request):
        return web.Response(
            text=query1_server_error_answer, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url)

    async with Client(transport=sample_transport,) as session:

        query = gql(query1_str)

        with pytest.raises(TransportQueryError):
            await session.execute(query)


invalid_protocol_responses = [
    "{}",
    "qlsjfqsdlkj",
    '{"not_data_or_errors": 35}',
]


@pytest.mark.asyncio
@pytest.mark.parametrize("response", invalid_protocol_responses)
async def test_aiohttp_invalid_protocol(event_loop, aiohttp_server, response):
    async def handler(request):
        return web.Response(text=response, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url)

    async with Client(transport=sample_transport,) as session:

        query = gql(query1_str)

        with pytest.raises(TransportProtocolError):
            await session.execute(query)


@pytest.mark.asyncio
async def test_aiohttp_subscribe_not_supported(event_loop, aiohttp_server):
    async def handler(request):
        return web.Response(text="does not matter", content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url)

    async with Client(transport=sample_transport,) as session:

        query = gql(query1_str)

        with pytest.raises(NotImplementedError):
            async for result in session.subscribe(query):
                pass


@pytest.mark.asyncio
async def test_aiohttp_cannot_connect_twice(event_loop, aiohttp_server):
    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url, timeout=10)

    async with Client(transport=sample_transport,) as session:

        with pytest.raises(TransportAlreadyConnected):
            await session.transport.connect()


@pytest.mark.asyncio
async def test_aiohttp_cannot_execute_if_not_connected(event_loop, aiohttp_server):
    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url, timeout=10)

    query = gql(query1_str)

    with pytest.raises(TransportClosed):
        await sample_transport.execute(query)


@pytest.mark.asyncio
async def test_aiohttp_extra_args(event_loop, aiohttp_server):
    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    # passing extra arguments to aiohttp.ClientSession
    jar = DummyCookieJar()
    sample_transport = AIOHTTPTransport(
        url=url, timeout=10, client_session_args={"version": "1.1", "cookie_jar": jar}
    )

    async with Client(transport=sample_transport,) as session:

        query = gql(query1_str)

        # Passing extra arguments to the post method of aiohttp
        result = await session.execute(query, extra_args={"allow_redirects": False})

        continents = result["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"


query2_str = """
    query getEurope ($code: ID!) {
      continent (code: $code) {
        name
      }
    }
"""

query2_server_answer = '{"data": {"continent": {"name": "Europe"}}}'


@pytest.mark.asyncio
async def test_aiohttp_query_variable_values(event_loop, aiohttp_server):
    async def handler(request):
        return web.Response(text=query2_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url, timeout=10)

    async with Client(transport=sample_transport,) as session:

        params = {"code": "EU"}

        query = gql(query2_str)

        # Execute query asynchronously
        result = await session.execute(
            query, variable_values=params, operation_name="getEurope"
        )

        continent = result["continent"]

        assert continent["name"] == "Europe"


@pytest.mark.asyncio
async def test_aiohttp_execute_running_in_thread(
    event_loop, aiohttp_server, run_sync_test
):
    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        sample_transport = AIOHTTPTransport(url=url)

        client = Client(transport=sample_transport)

        query = gql(query1_str)

        client.execute(query)

    await run_sync_test(event_loop, server, test_code)


@pytest.mark.asyncio
async def test_aiohttp_subscribe_running_in_thread(
    event_loop, aiohttp_server, run_sync_test
):
    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        sample_transport = AIOHTTPTransport(url=url)

        client = Client(transport=sample_transport)

        query = gql(query1_str)

        # Note: subscriptions are not supported on the aiohttp transport
        # But we add this test in order to have 100% code coverage
        # It is to check that we will correctly set an event loop
        # in the subscribe function if there is none (in a Thread for example)
        # We cannot test this with the websockets transport because
        # the websockets transport will set an event loop in its init

        with pytest.raises(NotImplementedError):
            for result in client.subscribe(query):
                pass

    await run_sync_test(event_loop, server, test_code)
