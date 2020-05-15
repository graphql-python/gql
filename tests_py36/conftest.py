import asyncio
import json
import logging
import os
import pathlib
import ssl
import types

import pytest
import websockets
from aiohttp.test_utils import TestServer as AIOHTTPTestServer
from websockets.exceptions import ConnectionClosed

from gql import Client
from gql.transport.websockets import WebsocketsTransport


def pytest_addoption(parser):
    parser.addoption(
        "--run-online",
        action="store_true",
        default=False,
        help="run tests necessitating online ressources",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "online: mark test as necessitating external online ressources"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-online"):
        # --run-online given in cli: do not skip online tests
        return
    skip_online = pytest.mark.skip(reason="need --run-online option to run")
    for item in items:
        if "online" in item.keywords:
            item.add_marker(skip_online)


@pytest.fixture
async def aiohttp_server():
    """Factory to create a TestServer instance, given an app.

    aiohttp_server(app, **kwargs)
    """
    servers = []

    async def go(app, *, port=None, **kwargs):  # type: ignore
        server = AIOHTTPTestServer(app, port=port)
        await server.start_server(**kwargs)
        servers.append(server)
        return server

    yield go

    while servers:
        await servers.pop().close()


# Adding debug logs to websocket tests
for name in ["websockets.server", "gql.transport.websockets"]:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if len(logger.handlers) < 1:
        logger.addHandler(logging.StreamHandler())

# Unit for timeouts. May be increased on slow machines by setting the
# GQL_TESTS_TIMEOUT_FACTOR environment variable.
# Copied from websockets source
MS = 0.001 * int(os.environ.get("GQL_TESTS_TIMEOUT_FACTOR", 1))


class TestServer:
    """
    Class used to generate a websocket server on localhost on a free port

    Will allow us to test our client by simulating different correct and incorrect server responses
    """

    def __init__(self, with_ssl: bool = False):
        self.with_ssl = with_ssl

    async def start(self, handler):

        print("Starting server")

        extra_serve_args = {}

        if self.with_ssl:
            # This is a copy of certificate from websockets tests folder
            #
            # Generate TLS certificate with:
            # $ openssl req -x509 -config test_localhost.cnf -days 15340 -newkey rsa:2048 \
            #       -out test_localhost.crt -keyout test_localhost.key
            # $ cat test_localhost.key test_localhost.crt > test_localhost.pem
            # $ rm test_localhost.key test_localhost.crt
            self.testcert = bytes(
                pathlib.Path(__file__).with_name("test_localhost.pem")
            )
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(self.testcert)

            extra_serve_args["ssl"] = ssl_context

        # Start a server with a random open port
        self.start_server = websockets.server.serve(
            handler, "localhost", 0, **extra_serve_args
        )

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
    async def send_keepalive(ws):
        await ws.send('{"type":"ka"}')

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


def get_server_handler(request):
    """ Get the server handler provided from test or use the default
    server handler if the test provides only an array of answers"""

    if isinstance(request.param, types.FunctionType):
        server_handler = request.param

    else:
        answers = request.param

        async def default_server_handler(ws, path):

            try:
                await TestServer.send_connection_ack(ws)
                query_id = 1

                for answer in answers:
                    result = await ws.recv()
                    print(f"Server received: {result}")

                    if isinstance(answer, str) and "{query_id}" in answer:
                        answer_format_params = {}
                        answer_format_params["query_id"] = query_id
                        formatted_answer = answer.format(**answer_format_params)
                    else:
                        formatted_answer = answer

                    await ws.send(formatted_answer)
                    await TestServer.send_complete(ws, query_id)
                    query_id += 1

                await TestServer.wait_connection_terminate(ws)
                await ws.wait_closed()
            except ConnectionClosed:
                pass

        server_handler = default_server_handler

    return server_handler


@pytest.fixture
async def ws_ssl_server(request):
    """websockets server fixture using ssl

    It can take as argument either a handler function for the websocket server for complete control
    OR an array of answers to be sent by the default server handler
    """

    server_handler = get_server_handler(request)

    try:
        test_server = TestServer(with_ssl=True)

        # Starting the server with the fixture param as the handler function
        await test_server.start(server_handler)

        yield test_server
    except Exception as e:
        print("Exception received in server fixture: " + str(e))
    finally:
        await test_server.stop()


@pytest.fixture
async def server(request):
    """server is a fixture used to start a dummy server to test the client behaviour.

    It can take as argument either a handler function for the websocket server for complete control
    OR an array of answers to be sent by the default server handler
    """

    server_handler = get_server_handler(request)

    try:
        test_server = TestServer()

        # Starting the server with the fixture param as the handler function
        await test_server.start(server_handler)

        yield test_server
    except Exception as e:
        print("Exception received in server fixture: " + str(e))
    finally:
        await test_server.stop()


@pytest.fixture
async def client_and_server(server):
    """client_and_server is a helper fixture to start a server and a client connected to its port"""

    # Generate transport to connect to the server fixture
    path = "/graphql"
    url = "ws://" + server.hostname + ":" + str(server.port) + path
    sample_transport = WebsocketsTransport(url=url)

    async with Client(transport=sample_transport) as session:

        # Yield both client session and server
        yield (session, server)
