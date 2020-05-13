import pytest
from aiohttp import web

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
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},{"code":"AS","name":"Asia"},'
    '{"code":"EU","name":"Europe"},{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
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
