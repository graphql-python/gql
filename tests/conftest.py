import asyncio
import json
import logging
import os
import pathlib
import ssl
import types
from concurrent.futures import ThreadPoolExecutor

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
        help="run tests necessitating online resources",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "online: mark test as necessitating external online resources"
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


class WebSocketServer:
    """Websocket server on localhost on a free port.

    This server allows us to test our client by simulating different correct and
    incorrect server responses.
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
            # $ openssl req -x509 -config test_localhost.cnf \
            #       -days 15340 -newkey rsa:2048 \
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
            handler, "127.0.0.1", 0, **extra_serve_args
        )

        # Wait that the server is started
        self.server = await self.start_server

        # Get hostname and port
        hostname, port = self.server.sockets[0].getsockname()[:2]
        assert hostname == "127.0.0.1"

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


class WebSocketServerHelper:
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


class PhoenixChannelServerHelper:
    @staticmethod
    async def send_close(ws):
        await ws.send('{"event":"phx_close"}')

    @staticmethod
    async def send_connection_ack(ws):

        # Line return for easy debugging
        print("")

        # Wait for init
        result = await ws.recv()
        json_result = json.loads(result)
        assert json_result["event"] == "phx_join"

        # Send ack
        await ws.send('{"event":"phx_reply", "payload": {"status": "ok"}, "ref": 1}')


def get_server_handler(request):
    """Get the server handler.

    Either get it from test or use the default server handler
    if the test provides only an array of answers.
    """

    if isinstance(request.param, types.FunctionType):
        server_handler = request.param

    else:
        answers = request.param

        async def default_server_handler(ws, path):

            try:
                await WebSocketServerHelper.send_connection_ack(ws)
                query_id = 1

                for answer in answers:
                    result = await ws.recv()
                    print(f"Server received: {result}")

                    if isinstance(answer, str) and "{query_id}" in answer:
                        answer_format_params = {"query_id": query_id}
                        formatted_answer = answer.format(**answer_format_params)
                    else:
                        formatted_answer = answer

                    await ws.send(formatted_answer)
                    await WebSocketServerHelper.send_complete(ws, query_id)
                    query_id += 1

                await WebSocketServerHelper.wait_connection_terminate(ws)
                await ws.wait_closed()
            except ConnectionClosed:
                pass

        server_handler = default_server_handler

    return server_handler


@pytest.fixture
async def ws_ssl_server(request):
    """Websockets server fixture using SSL.

    It can take as argument either a handler function for the websocket server for
    complete control OR an array of answers to be sent by the default server handler.
    """

    server_handler = get_server_handler(request)

    try:
        test_server = WebSocketServer(with_ssl=True)

        # Starting the server with the fixture param as the handler function
        await test_server.start(server_handler)

        yield test_server
    except Exception as e:
        print("Exception received in ws server fixture:", e)
    finally:
        await test_server.stop()


@pytest.fixture
async def server(request):
    """Fixture used to start a dummy server to test the client behaviour.

    It can take as argument either a handler function for the websocket server for
    complete control OR an array of answers to be sent by the default server handler.
    """

    server_handler = get_server_handler(request)

    try:
        test_server = WebSocketServer()

        # Starting the server with the fixture param as the handler function
        await test_server.start(server_handler)

        yield test_server
    except Exception as e:
        print("Exception received in server fixture:", e)
    finally:
        await test_server.stop()


@pytest.fixture
async def client_and_server(server):
    """Helper fixture to start a server and a client connected to its port."""

    # Generate transport to connect to the server fixture
    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"
    sample_transport = WebsocketsTransport(url=url)

    async with Client(transport=sample_transport) as session:

        # Yield both client session and server
        yield session, server


@pytest.fixture
async def run_sync_test():
    async def run_sync_test_inner(event_loop, server, test_function):
        """This function will run the test in a different Thread.

        This allows us to run sync code while aiohttp server can still run.
        """
        executor = ThreadPoolExecutor(max_workers=2)
        test_task = event_loop.run_in_executor(executor, test_function)

        await test_task

        if hasattr(server, "close"):
            await server.close()

    return run_sync_test_inner
