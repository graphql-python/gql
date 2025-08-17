import asyncio
import json
import logging
import os
import pathlib
import platform
import re
import ssl
import sys
import tempfile
import types
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable, List, Union, cast

import pytest
import pytest_asyncio
from _pytest.fixtures import SubRequest

from gql import Client

all_transport_dependencies = ["aiohttp", "requests", "httpx", "websockets", "botocore"]


PyPy = platform.python_implementation() == "PyPy"


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
    # --httpx-only
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


@pytest_asyncio.fixture
async def aiohttp_server():
    async for server in aiohttp_server_base():
        yield server


@pytest_asyncio.fixture
async def ssl_aiohttp_server():
    async for server in aiohttp_server_base(with_ssl=True):
        yield server


# Adding debug logs
for name in [
    "websockets.legacy.server",
    "gql.transport.aiohttp",
    "gql.transport.aiohttp_websockets",
    "gql.transport.appsync",
    "gql.transport.common.base",
    "gql.transport.httpx",
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


def get_localhost_ssl_context_client():
    """
    Create a client-side SSL context that verifies the specific self-signed certificate
    used for our test.
    """
    # Get the certificate from the server setup
    cert_path = bytes(pathlib.Path(__file__).with_name("test_localhost_client.crt"))

    # Create client SSL context
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    # Load just the certificate part as a trusted CA
    ssl_context.load_verify_locations(cafile=cert_path)

    # Require certificate verification
    ssl_context.verify_mode = ssl.CERT_REQUIRED

    # Enable hostname checking for localhost
    ssl_context.check_hostname = True

    return cert_path, ssl_context


class WebSocketServer:
    """Websocket server on localhost on a free port.

    This server allows us to test our client by simulating different correct and
    incorrect server responses.
    """

    def __init__(self, with_ssl: bool = False):
        self.with_ssl = with_ssl

    async def start(self, handler, extra_serve_args=None):

        import websockets

        print("Starting server")

        if extra_serve_args is None:
            extra_serve_args = {}

        if self.with_ssl:
            self.testcert, ssl_context = get_localhost_ssl_context()
            extra_serve_args["ssl"] = ssl_context

        # Adding dummy response headers
        extra_headers = {"dummy": "test1234"}

        def process_response(connection, request, response):
            response.headers.update(extra_headers)
            return response

        # Start a server with a random open port
        self.server = await websockets.serve(
            handler,
            "127.0.0.1",
            0,
            process_response=process_response,
            **extra_serve_args,
        )

        # Get hostname and port
        hostname, port = self.server.sockets[0].getsockname()[:2]  # type: ignore
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
            pass

        print("Server stopped\n\n\n")


class AIOHTTPWebsocketServer:
    def __init__(self, with_ssl=False):
        self.runner = None
        self.site = None
        self.port = None
        self.hostname = "127.0.0.1"
        self.with_ssl = with_ssl
        self.ssl_context = None
        if with_ssl:
            _, self.ssl_context = get_localhost_ssl_context()

    def get_default_server_handler(answers: Iterable[str]) -> Callable:
        async def default_server_handler(request):

            import aiohttp
            import aiohttp.web
            from aiohttp import WSMsgType

            ws = aiohttp.web.WebSocketResponse()
            ws.headers.update({"dummy": "test1234"})
            await ws.prepare(request)

            try:
                # Init and ack
                msg = await ws.__anext__()
                assert msg.type == WSMsgType.TEXT
                result = msg.data
                json_result = json.loads(result)
                assert json_result["type"] == "connection_init"
                await ws.send_str('{"type":"connection_ack"}')
                query_id = 1

                # Wait for queries and send answers
                for answer in answers:
                    msg = await ws.__anext__()
                    if msg.type == WSMsgType.TEXT:
                        result = msg.data

                        print(f"Server received: {result}", file=sys.stderr)
                        if isinstance(answer, str) and "{query_id}" in answer:
                            answer_format_params = {"query_id": query_id}
                            formatted_answer = answer.format(**answer_format_params)
                        else:
                            formatted_answer = answer
                        await ws.send_str(formatted_answer)
                        await ws.send_str(
                            f'{{"type":"complete","id":"{query_id}","payload":null}}'
                        )
                        query_id += 1

                    elif msg.type == WSMsgType.ERROR:
                        print(f"WebSocket connection closed with: {ws.exception()}")
                        raise ws.exception()  # type: ignore
                    elif msg.type in (
                        WSMsgType.CLOSE,
                        WSMsgType.CLOSED,
                        WSMsgType.CLOSING,
                    ):
                        print("WebSocket connection closed")
                        raise ConnectionResetError

                # Wait for connection_terminate
                msg = await ws.__anext__()
                result = msg.data
                json_result = json.loads(result)
                assert json_result["type"] == "connection_terminate"

                # Wait for connection close
                msg = await ws.__anext__()

            except ConnectionResetError:
                pass

            except Exception as e:
                print(f"Server exception {e!s}", file=sys.stderr)

            await ws.close()
            return ws

        return default_server_handler

    async def shutdown_server(self, app):
        print("Shutting down server...")
        await app.shutdown()
        await app.cleanup()

    async def start(self, handler):
        import aiohttp
        import aiohttp.web

        app = aiohttp.web.Application()
        app.router.add_get("/graphql", handler)
        self.runner = aiohttp.web.AppRunner(app)
        await self.runner.setup()

        # Use port 0 to bind to an available port
        self.site = aiohttp.web.TCPSite(
            self.runner, self.hostname, 0, ssl_context=self.ssl_context
        )
        await self.site.start()

        # Retrieve the actual port the server is listening on
        assert self.site._server is not None
        sockets = self.site._server.sockets  # type: ignore
        if sockets:
            self.port = sockets[0].getsockname()[1]
            protocol = "https" if self.with_ssl else "http"
            print(f"Server started at {protocol}://{self.hostname}:{self.port}")

    async def stop(self):
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()


@pytest_asyncio.fixture
async def aiohttp_ws_server(request):
    """Fixture used to start a dummy server to test the client behaviour
    using the aiohttp dependency.

    It can take as argument either a handler function for the websocket server for
    complete control OR an array of answers to be sent by the default server handler.
    """

    server_handler = get_aiohttp_ws_server_handler(request)

    try:
        test_server = AIOHTTPWebsocketServer()

        # Starting the server with the fixture param as the handler function
        await test_server.start(server_handler)

        yield test_server
    except Exception as e:
        print("Exception received in server fixture:", e)
    finally:
        await test_server.stop()


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

    def __init__(self, content: Union[str, bytearray, bytes]):

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


def get_aiohttp_ws_server_handler(
    request: SubRequest,
) -> Callable:
    """Get the server handler for the aiohttp websocket server.

    Either get it from test or use the default server handler
    if the test provides only an array of answers.
    """

    server_handler: Callable

    if isinstance(request.param, types.FunctionType):
        server_handler = request.param

    else:
        answers = cast(List[str], request.param)
        server_handler = AIOHTTPWebsocketServer.get_default_server_handler(answers)

    return server_handler


def get_server_handler(
    request: SubRequest,
) -> Callable:
    """Get the server handler.

    Either get it from test or use the default server handler
    if the test provides only an array of answers.
    """

    from websockets.exceptions import ConnectionClosed

    if isinstance(request.param, types.FunctionType):
        server_handler: Callable = request.param

    else:
        answers = request.param

        async def default_server_handler(ws):

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


@pytest_asyncio.fixture
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


@pytest_asyncio.fixture
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


@pytest_asyncio.fixture
async def graphqlws_server(request):
    """Fixture used to start a dummy server with the graphql-ws protocol.

    Similar to the server fixture above but will return "graphql-transport-ws"
    as the server subprotocol.

    It can take as argument either a handler function for the websocket server for
    complete control OR an array of answers to be sent by the default server handler.
    """

    subprotocol = "graphql-transport-ws"

    server_handler = get_server_handler(request)

    try:
        test_server = WebSocketServer()

        # Starting the server with the fixture param as the handler function
        await test_server.start(
            server_handler, extra_serve_args={"subprotocols": [subprotocol]}
        )

        yield test_server
    except Exception as e:
        print("Exception received in server fixture:", e)
    finally:
        await test_server.stop()


@pytest_asyncio.fixture
async def client_and_server(server):
    """Helper fixture to start a server and a client connected to its port."""

    from gql.transport.websockets import WebsocketsTransport

    # Generate transport to connect to the server fixture
    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"
    transport = WebsocketsTransport(url=url)

    async with Client(transport=transport) as session:

        # Yield both client session and server
        yield session, server


@pytest_asyncio.fixture
async def aiohttp_client_and_server(server):
    """
    Helper fixture to start a server and a client connected to its port
    with an aiohttp websockets transport.
    """

    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    # Generate transport to connect to the server fixture
    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"
    transport = AIOHTTPWebsocketsTransport(url=url)

    async with Client(transport=transport) as session:

        # Yield both client session and server
        yield session, server


@pytest_asyncio.fixture
async def aiohttp_client_and_aiohttp_ws_server(aiohttp_ws_server):
    """
    Helper fixture to start an aiohttp websocket server and
    a client connected to its port with an aiohttp websockets transport.
    """

    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    server = aiohttp_ws_server

    # Generate transport to connect to the server fixture
    path = "/graphql"
    url = f"ws://{server.hostname}:{server.port}{path}"
    transport = AIOHTTPWebsocketsTransport(url=url)

    async with Client(transport=transport) as session:

        # Yield both client session and server
        yield session, server


@pytest_asyncio.fixture
async def client_and_graphqlws_server(graphqlws_server):
    """Helper fixture to start a server with the graphql-ws prototocol
    and a client connected to its port."""

    from gql.transport.websockets import WebsocketsTransport

    # Generate transport to connect to the server fixture
    path = "/graphql"
    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}{path}"
    transport = WebsocketsTransport(
        url=url,
        subprotocols=[WebsocketsTransport.GRAPHQLWS_SUBPROTOCOL],
    )

    async with Client(transport=transport) as session:

        # Yield both client session and server
        yield session, graphqlws_server


@pytest_asyncio.fixture
async def client_and_aiohttp_websocket_graphql_server(graphqlws_server):
    """Helper fixture to start a server with the graphql-ws prototocol
    and a client connected to its port."""

    from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

    # Generate transport to connect to the server fixture
    path = "/graphql"
    url = f"ws://{graphqlws_server.hostname}:{graphqlws_server.port}{path}"
    transport = AIOHTTPWebsocketsTransport(
        url=url,
        subprotocols=[AIOHTTPWebsocketsTransport.GRAPHQLWS_SUBPROTOCOL],
    )

    async with Client(transport=transport) as session:

        # Yield both client session and server
        yield session, graphqlws_server


@pytest_asyncio.fixture
async def run_sync_test():
    async def run_sync_test_inner(server, test_function):
        """This function will run the test in a different Thread.

        This allows us to run sync code while aiohttp server can still run.
        """
        event_loop = asyncio.get_running_loop()
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


def strip_braces_spaces(s):
    """Allow to ignore differences in graphql-core syntax between versions"""

    # Strip spaces after starting braces
    strip_front = s.replace("{ ", "{")

    # Strip spaces before closing braces only if one space is present
    strip_back = re.sub(r"([^\s]) }", r"\1}", strip_front)

    return strip_back


def make_upload_handler(
    nb_files=1,
    filenames=None,
    request_headers=None,
    file_headers=None,
    binary=False,
    expected_contents=None,
    expected_operations=None,
    expected_map=None,
    server_answer='{"data":{"success":true}}',
):
    assert expected_contents is not None
    assert expected_operations is not None
    assert expected_map is not None

    async def single_upload_handler(request):
        from aiohttp import web

        reader = await request.multipart()

        if request_headers is not None:
            for k, v in request_headers.items():
                assert request.headers[k] == v

        field_0 = await reader.next()
        assert field_0.name == "operations"
        field_0_text = await field_0.text()
        assert strip_braces_spaces(field_0_text) == expected_operations

        field_1 = await reader.next()
        assert field_1.name == "map"
        field_1_text = await field_1.text()
        assert field_1_text == expected_map

        for i in range(nb_files):
            field = await reader.next()
            assert field.name == str(i)
            if filenames is not None:
                assert field.filename == filenames[i]

            if binary:
                field_content = await field.read()
                assert field_content == expected_contents[i]
            else:
                field_text = await field.text()
                assert field_text == expected_contents[i]

            if file_headers is not None:
                for k, v in file_headers[i].items():
                    assert field.headers[k] == v

        final_field = await reader.next()
        assert final_field is None

        return web.Response(text=server_answer, content_type="application/json")

    return single_upload_handler
