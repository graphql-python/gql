import websockets
import asyncio
import json
import os
import pytest
import logging

from gql.transport.websockets import WebsocketsTransport
from gql import AsyncClient

# Adding debug logs to websocket tests
for name in ["websockets.server", "gql.transport.websockets"]:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if len(logger.handlers) < 1:
        logger.addHandler(logging.StreamHandler())

# Unit for timeouts. May be increased on slow machines by setting the
# WEBSOCKETS_TESTS_TIMEOUT_FACTOR environment variable.
MS = 0.001 * int(os.environ.get("WEBSOCKETS_TESTS_TIMEOUT_FACTOR", 1))


class TestServer:
    """
    Class used to generate a websocket server on localhost on a free port

    Will allow us to test our client by simulating different correct and incorrect server responses
    """

    async def start(self, handler):

        print("Starting server")

        # Start a server with a random open port
        self.start_server = websockets.server.serve(handler, "localhost", 0)

        # Wait that the server is started
        self.server = await self.start_server

        # Get hostname and port
        hostname, port = self.server.sockets[0].getsockname()

        self.hostname = hostname
        self.port = port

        print(f"Server started on port {port}")

    async def stop(self):
        print("Stopping server")

        self.server.close()
        try:
            await asyncio.wait_for(self.server.wait_closed(), timeout=1)
        except asyncio.TimeoutError:  # pragma: no cover
            assert False, "Server failed to stop"

        print("Server stopped\n\n\n")

    @staticmethod
    async def send_complete(ws, query_id):
        await ws.send(f'{{"type":"complete","id":"{query_id}","payload":null}}')

    @staticmethod
    async def send_connection_ack(ws):

        # Line return for easy debugging
        print("")

        # Wait for init
        result = await ws.recv()
        json_result = json.loads(result)
        assert json_result["type"] == "connection_init"

        # Send ack
        await ws.send('{"type":"connection_ack"}')

    @staticmethod
    async def wait_connection_terminate(ws):
        result = await ws.recv()
        json_result = json.loads(result)
        assert json_result["type"] == "connection_terminate"


@pytest.fixture
async def server(request):
    try:
        test_server = TestServer()

        # Starting the server with the fixture param as the handler function
        await test_server.start(request.param)

        yield test_server
    except Exception as e:
        print("Exception received in server fixture: " + str(e))
    finally:
        await test_server.stop()


@pytest.fixture
async def client_and_server(server):

    # Generate transport to connect to the server fixture
    path = "/graphql"
    url = "ws://" + server.hostname + ":" + str(server.port) + path
    sample_transport = WebsocketsTransport(url=url)

    async with AsyncClient(transport=sample_transport) as client:

        # Yield both client and server
        yield (client, server)
