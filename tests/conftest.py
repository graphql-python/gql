import asyncio
import json
import logging
import os
import pathlib
import ssl
import sys
import tempfile
import types
from concurrent.futures import ThreadPoolExecutor
from typing import Union

import pytest

from gql import Client

all_transport_dependencies = ["aiohttp", "requests", "websockets", "botocore"]


def pytest_addoption(parser):
    parser.addoption(
        "--run-online",
        action="store_true",
        default=False,
        help="run tests necessitating online resources",
    )
    for transport in all_transport_dependencies:
        parser.addoption(
            f"--{transport}-only",
            action="store_true",
            default=False,
            help=f"run tests necessitating only the {transport} dependency",
        )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "online: mark test as necessitating external online resources"
    )
    for transport in all_transport_dependencies:
        config.addinivalue_line(
            "markers",
            f"{transport}: mark test as necessitating the {transport} dependency",
        )


def pytest_collection_modifyitems(config, items):

    # --run-online given in cli: do not skip online tests
    if not config.getoption("--run-online"):
        skip_online = pytest.mark.skip(reason="need --run-online option to run")
        for item in items:
            if "online" in item.keywords:
                item.add_marker(skip_online)

    # --aiohttp-only
    # --requests-only
    # --websockets-only
    for transport in all_transport_dependencies:

        other_transport_dependencies = [
            t for t in all_transport_dependencies if t != transport
        ]

        if config.getoption(f"--{transport}-only"):
            skip_transport = pytest.mark.skip(
                reason=f"need another dependency than {transport}"
            )
            for item in items:
                # Check if we have a dependency transport
                # other than the requested transport
                if any(t in item.keywords for t in other_transport_dependencies):
                    item.add_marker(skip_transport)


async def aiohttp_server_base(with_ssl=False):
    """Factory to create a TestServer instance, given an app.

    aiohttp_server(app, **kwargs)
    """
    from aiohttp.test_utils import TestServer as AIOHTTPTestServer

    servers = []

    async def go(app, *, port=None, **kwargs):  # type: ignore
        server = AIOHTTPTestServer(app, port=port)

        start_server_args = {**kwargs}
        if with_ssl:
            testcert, ssl_context = get_localhost_ssl_context()
            start_server_args["ssl"] = ssl_context

        await server.start_server(**start_server_args)
        servers.append(server)
        return server

    yield go

    while servers:
        await servers.pop().close()


@pytest.fixture
async def aiohttp_server():
    async for server in aiohttp_server_base():
        yield server


@pytest.fixture
async def ssl_aiohttp_server():
    async for server in aiohttp_server_base(with_ssl=True):
        yield server


# Adding debug logs
for name in [
    "websockets.legacy.server",
    "gql.transport.aiohttp",
    "gql.transport.appsync",
    "gql.transport.phoenix_channel_websockets",
    "gql.transport.requests",
    "gql.transport.websockets",
    "gql.dsl",
    "gql.utilities.parse_result",
]:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if len(logger.handlers) < 1:
        logger.addHandler(logging.StreamHandler())

# Unit for timeouts. May be increased on slow machines by setting the
# GQL_TESTS_TIMEOUT_FACTOR environment variable.
# Copied from websockets source
MS = 0.001 * int(os.environ.get("GQL_TESTS_TIMEOUT_FACTOR", 1))


def get_localhost_ssl_context():
    # This is a copy of certificate from websockets tests folder
    #
    # Generate TLS certificate with:
    # $ openssl req -x509 -config test_localhost.cnf \
    #       -days 15340 -newkey rsa:2048 \
    #       -out test_localhost.crt -keyout test_localhost.key
    # $ cat test_localhost.key test_localhost.crt > test_localhost.pem
    # $ rm test_localhost.key test_localhost.crt
    testcert = bytes(pathlib.Path(__file__).with_name("test_localhost.pem"))
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(testcert)

    return (testcert, ssl_context)


class WebSocketServer:
    """Websocket server on localhost on a free port.

    This server allows us to test our client by simulating different correct and
    incorrect server responses.
    """

    def __init__(self, with_ssl: bool = False):
        self.with_ssl = with_ssl

    async def start(self, handler, extra_serve_args=None):

        import websockets.server

        print("Starting server")

        if extra_serve_args is None:
            extra_serve_args = {}

        if self.with_ssl:
            self.testcert, ssl_context = get_localhost_ssl_context()
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
            await asyncio.wait_for(self.server.wait_closed(), timeout=5)
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
    async def send_ping(ws, payload=None):
        if payload is None:
            await ws.send('{"type":"ping"}')
        else:
            await ws.send(json.dumps({"type": "ping", "payload": payload}))

    @staticmethod
    async def send_pong(ws, payload=None):
        if payload is None:
            await ws.send('{"type":"pong"}')
        else:
            await ws.send(json.dumps({"type": "pong", "payload": payload}))

    @staticmethod
    async def send_connection_ack(ws, payload=None):

        # Line return for easy debugging
        print("")

        # Wait for init
        result = await ws.recv()
        json_result = json.loads(result)
        assert json_result["type"] == "connection_init"

        # Send ack
        if payload is None:
            await ws.send('{"type":"connection_ack"}')
        else:
            await ws.send(json.dumps({"type": "connection_ack", "payload": payload}))

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


class TemporaryFile:
    """Class used to generate temporary files for the tests"""

    def __init__(self, content: Union[str, bytearray]):

        mode = "w" if isinstance(content, str) else "wb"

        # We need to set the newline to '' so that the line returns
        # are not replaced by '\r\n' on windows
        newline = "" if isinstance(content, str) else None

        self.file = tempfile.NamedTemporaryFile(
            mode=mode, newline=newline, delete=False
        )

        with self.file as f:
            f.write(content)

    @property
    def filename(self):
        return self.file.name

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        os.unlink(self.filename)


def get_server_handler(request):
    """Get the server handler.

    Either get it from test or use the default server handler
    if the test provides only an array of answers.
    """

    from websockets.exceptions import ConnectionClosed

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
                    print(f"Server received: {result}", file=sys.stderr)

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
async def graphqlws_server(request):
    """Fixture used to start a dummy server with the graphql-ws protocol.

    Similar to the server fixture above but will return "graphql-transport-ws"
    as the server subprotocol.

    It can take as argument either a handler function for the websocket server for
    complete control OR an array of answers to be sent by the default server handler.
    """

    subprotocol = "graphql-transport-ws"

    from websockets.server import WebSocketServerProtocol

    class CustomSubprotocol(WebSocketServerProtocol):
        def select_subprotocol(self, client_subprotocols, server_subprotocols):
            print(f"Client subprotocols: {client_subprotocols!r}")
            print(f"Server subprotocols: {server_subprotocols!r}")

            return subprotocol

        def process_subprotocol(self, headers, available_subprotocols):
            # Overwriting available subprotocols
            available_subprotocols = [subprotocol]

            print(f"headers: {headers!r}")
            # print (f"Available subprotocols: {available_subprotocols!r}")

            return super().process_subprotocol(headers, available_subprotocols)

    server_handler = get_server_handler(request)

    try:
        test_server = WebSocketServer()

        # Starting the server with the fixture param as the handler function
        await test_server.start(
            server_handler, extra_serve_args={"create_protocol": CustomSubprotocol}
        )

        yield test_server
    except Exception as e:
        print("Exception received in server fixture:", e)
    finally:
        await test_server.stop()


@pytest.fixture
async def client_and_server(server):
    """Helper fixture to start a server and a client connected to its port."""

    from gql.transport.websockets import WebsocketsTransport

    # Generate transport to connect to the server fixture
    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"
    sample_transport = WebsocketsTransport(url=url)

    async with Client(transport=sample_transport) as session:

        # Yield both client session and server
        yield session, server


@pytest.fixture
async def client_and_graphqlws_server(graphqlws_server):
    """Helper fixture to start a server with the graphql-ws prototocol
    and a client connected to its port."""

    from gql.transport.websockets import WebsocketsTransport

    # Generate transport to connect to the server fixture
    path = "/graphql"
    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}{path}"
    sample_transport = WebsocketsTransport(url=url)

    async with Client(transport=sample_transport) as session:

        # Yield both client session and server
        yield session, graphqlws_server


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


pytest_plugins = [
    "tests.fixtures.aws.fake_credentials",
    "tests.fixtures.aws.fake_request",
    "tests.fixtures.aws.fake_session",
    "tests.fixtures.aws.fake_signer",
]
