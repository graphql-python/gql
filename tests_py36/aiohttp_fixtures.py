import pytest
import asyncio

from aiohttp.test_utils import TestServer


@pytest.fixture
async def aiohttp_server():
    """Factory to create a TestServer instance, given an app.

    aiohttp_server(app, **kwargs)
    """
    servers = []

    async def go(app, *, port=None, **kwargs):  # type: ignore
        server = TestServer(app, port=port)
        await server.start_server(**kwargs)
        servers.append(server)
        return server

    yield go

    while servers:
        await servers.pop().close()
