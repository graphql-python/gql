import asyncio
import json
import pytest
import types
from typing import List

from gql import Client, gql
from gql.transport.exceptions import (
    TransportAlreadyConnected,
    TransportClosed,
    TransportProtocolError,
    TransportQueryError,
)

from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

from .conftest import MS, WebSocketServerHelper

# Marking all tests in this file with the websockets marker
pytestmark = pytest.mark.aiohttp_websockets

invalid_query_str = """
    query getContinents {
      continents {
        code
        bloh
      }
    }
"""

invalid_query1_server_answer = (
    '{{"type":"data","id":"{query_id}",'
    '"payload":{{"errors":['
    '{{"message":"Cannot query field \\"bloh\\" on type \\"Continent\\".",'
    '"locations":[{{"line":4,"column":5}}],'
    '"extensions":{{"code":"INTERNAL_SERVER_ERROR"}}}}]}}}}'
)

invalid_query1_server = [invalid_query1_server_answer]

@pytest.mark.asyncio
@pytest.mark.parametrize("aiohttp_server", [invalid_query1_server], indirect=True)
@pytest.mark.parametrize("query_str", [invalid_query_str])
async def test_aiohttp_websocket_invalid_query(event_loop, aiohttp_server, query_str: str,):
    
    from aiohttp import web

    async def handler(request):
        return web.Response(
            text=invalid_query1_server_answer,
            content_type="application/json",
            headers={"dummy": "this should not be returned"},
        )
    
    app = web.Application()
    app.router.add_get("/ws", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/ws")

    transport = AIOHTTPWebsocketsTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:


        query = gql(query_str)

        with pytest.raises(TransportQueryError) as exc_info:
            await session.execute(query)

        exception = exc_info.value

        assert isinstance(exception.errors, List)

        error = exception.errors[0]

        assert error["extensions"]["code"] == "INTERNAL_SERVER_ERROR"