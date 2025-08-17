import io
import json
from typing import Any, Dict, Mapping

import pytest

from gql import Client, FileVar, gql
from gql.cli import get_parser, main
from gql.transport.exceptions import (
    TransportAlreadyConnected,
    TransportClosed,
    TransportConnectionFailed,
    TransportProtocolError,
    TransportQueryError,
    TransportServerError,
)

from .conftest import (
    TemporaryFile,
    get_localhost_ssl_context_client,
    make_upload_handler,
)

query1_str = """
    query getContinents {
      continents {
        code
        name
      }
    }
"""

query1_server_answer_data = (
    '{"continents":['
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
    '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
    '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
    '{"code":"SA","name":"South America"}]}'
)


query1_server_answer = f'{{"data":{query1_server_answer_data}}}'

# Marking all tests in this file with the httpx marker
pytestmark = pytest.mark.httpx


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_query(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer,
            content_type="application/json",
            headers={"dummy": "test1234"},
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:

        query = gql(query1_str)

        # Execute query asynchronously
        result = await session.execute(query)

        continents = result["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"

        # Checking response headers are saved in the transport
        assert hasattr(transport, "response_headers")
        assert isinstance(transport.response_headers, Mapping)
        assert transport.response_headers["dummy"] == "test1234"


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_ignore_backend_content_type(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="text/plain")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:

        query = gql(query1_str)

        result = await session.execute(query)

        continents = result["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_cookies(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        assert "COOKIE" in request.headers
        assert "cookie1=val1" == request.headers["COOKIE"]

        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url, cookies={"cookie1": "val1"})

    async with Client(transport=transport) as session:

        query = gql(query1_str)

        # Execute query asynchronously
        result = await session.execute(query)

        continents = result["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_error_code_401(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

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

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url)

    async with Client(transport=transport) as session:

        query = gql(query1_str)

        with pytest.raises(TransportServerError) as exc_info:
            await session.execute(query)

        assert "Client error '401 Unauthorized'" in str(exc_info.value)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_error_code_429(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        # Will generate http error code 429
        return web.Response(
            text="""
<html>
  <head>
     <title>Too Many Requests</title>
  </head>
  <body>
     <h1>Too Many Requests</h1>
     <p>I only allow 50 requests per hour to this Web site per
        logged in user.  Try again soon.</p>
  </body>
</html>""",
            content_type="text/html",
            status=429,
            headers={"Retry-After": "3600"},
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url)

    async with Client(transport=transport) as session:

        query = gql(query1_str)

        with pytest.raises(TransportServerError) as exc_info:
            await session.execute(query)

        assert "Client error '429 Too Many Requests'" in str(exc_info.value)

        # Checking response headers are saved in the transport
        assert hasattr(transport, "response_headers")
        assert isinstance(transport.response_headers, Mapping)
        assert transport.response_headers["Retry-After"] == "3600"


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_error_code_500(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        # Will generate http error code 500
        raise Exception("Server error")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url)

    async with Client(transport=transport) as session:

        query = gql(query1_str)

        with pytest.raises(TransportServerError) as exc_info:
            await session.execute(query)

        assert "Server error '500 Internal Server Error'" in str(exc_info.value)


transport_query_error_responses = [
    '{"errors": ["Error 1", "Error 2"]}',
    '{"errors": {"error_1": "Something"}}',
    '{"errors": 5}',
]


@pytest.mark.aiohttp
@pytest.mark.asyncio
@pytest.mark.parametrize("query_error", transport_query_error_responses)
async def test_httpx_error_code(aiohttp_server, query_error):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(text=query_error, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url)

    async with Client(transport=transport) as session:

        query = gql(query1_str)

        with pytest.raises(TransportQueryError):
            await session.execute(query)


invalid_protocol_responses = [
    {
        "response": "{}",
        "expected_exception": (
            "Server did not return a GraphQL result: "
            'No "data" or "errors" keys in answer: {}'
        ),
    },
    {
        "response": "qlsjfqsdlkj",
        "expected_exception": (
            "Server did not return a GraphQL result: Not a JSON answer: qlsjfqsdlkj"
        ),
    },
    {
        "response": '{"not_data_or_errors": 35}',
        "expected_exception": (
            "Server did not return a GraphQL result: "
            'No "data" or "errors" keys in answer: {"not_data_or_errors": 35}'
        ),
    },
    {
        "response": "",
        "expected_exception": (
            "Server did not return a GraphQL result: Not a JSON answer: "
        ),
    },
]


@pytest.mark.aiohttp
@pytest.mark.asyncio
@pytest.mark.parametrize("param", invalid_protocol_responses)
async def test_httpx_invalid_protocol(aiohttp_server, param):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    response = param["response"]

    async def handler(request):
        return web.Response(text=response, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url)

    async with Client(transport=transport) as session:

        query = gql(query1_str)

        with pytest.raises(TransportProtocolError) as exc_info:
            await session.execute(query)

        assert param["expected_exception"] in str(exc_info.value)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_subscribe_not_supported(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(text="does not matter", content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url)

    async with Client(transport=transport) as session:

        query = gql(query1_str)

        with pytest.raises(NotImplementedError):
            async for result in session.subscribe(query):
                pass


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_cannot_connect_twice(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:

        with pytest.raises(TransportAlreadyConnected):
            await session.transport.connect()


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_cannot_execute_if_not_connected(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url, timeout=10)

    query = gql(query1_str)

    with pytest.raises(TransportClosed):
        await transport.execute(query)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_extra_args(aiohttp_server):
    import httpx
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    # passing extra arguments to httpx.AsyncClient
    inner_transport = httpx.AsyncHTTPTransport(retries=2)
    transport = HTTPXAsyncTransport(url=url, max_redirects=2, transport=inner_transport)

    async with Client(transport=transport) as session:

        query = gql(query1_str)

        # Passing extra arguments to the post method
        result = await session.execute(query, extra_args={"follow_redirects": True})

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


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_query_variable_values(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(text=query2_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:

        query = gql(query2_str)

        query.variable_values = {"code": "EU"}
        query.operation_name = "getEurope"

        # Execute query asynchronously
        result = await session.execute(query)

        continent = result["continent"]

        assert continent["name"] == "Europe"


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_query_variable_values_fix_issue_292(aiohttp_server):
    """Allow to specify variable_values without keyword.

    See https://github.com/graphql-python/gql/issues/292"""

    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(text=query2_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:

        query = gql(query2_str)

        query.variable_values = {"code": "EU"}
        query.operation_name = "getEurope"

        # Execute query asynchronously
        result = await session.execute(query)

        continent = result["continent"]

        assert continent["name"] == "Europe"


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_execute_running_in_thread(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    def test_code():
        transport = HTTPXAsyncTransport(url=url)

        client = Client(transport=transport)

        query = gql(query1_str)

        client.execute(query)

    await run_sync_test(server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_subscribe_running_in_thread(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    def test_code():
        transport = HTTPXAsyncTransport(url=url)

        client = Client(transport=transport)

        query = gql(query1_str)

        # Note: subscriptions are not supported on the httpx transport
        # But we add this test in order to have 100% code coverage
        # It is to check that we will correctly set an event loop
        # in the subscribe function if there is none (in a Thread for example)
        # We cannot test this with the websockets transport because
        # the websockets transport will set an event loop in its init

        with pytest.raises(NotImplementedError):
            for result in client.subscribe(query):
                pass

    await run_sync_test(server, test_code)


file_upload_mutation_1 = """
    mutation($file: Upload!) {
      uploadFile(input:{other_var:$other_var, file:$file}) {
        success
      }
    }
"""

file_upload_mutation_1_operations = (
    '{"query": "mutation ($file: Upload!) {\\n  uploadFile(input: {other_var: '
    '$other_var, file: $file}) {\\n    success\\n  }\\n}", "variables": '
    '{"file": null, "other_var": 42}}'
)

file_upload_mutation_1_map = '{"0": ["variables.file"]}'

file_1_content = """
This is a test file
This file will be sent in the GraphQL mutation
"""


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_file_upload(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    app = web.Application()
    app.router.add_route(
        "POST",
        "/",
        make_upload_handler(
            expected_map=file_upload_mutation_1_map,
            expected_operations=file_upload_mutation_1_operations,
            expected_contents=[file_1_content],
        ),
    )
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url, timeout=10)

    with TemporaryFile(file_1_content) as test_file:

        async with Client(transport=transport) as session:

            query = gql(file_upload_mutation_1)

            file_path = test_file.filename

            # Using an opened file
            with open(file_path, "rb") as f:

                query.variable_values = {"file": f, "other_var": 42}

                # Execute query asynchronously
                with pytest.warns(
                    DeprecationWarning,
                    match="Not using FileVar for file upload is deprecated",
                ):
                    result = await session.execute(query, upload_files=True)

            success = result["success"]
            assert success

            # Using an opened file inside a FileVar object
            with open(file_path, "rb") as f:

                query.variable_values = {"file": FileVar(f), "other_var": 42}

                # Execute query asynchronously
                result = await session.execute(query, upload_files=True)

            success = result["success"]
            assert success

            # Using an filename string inside a FileVar object
            query.variable_values = {"file": FileVar(file_path), "other_var": 42}

            # Execute query asynchronously
            result = await session.execute(query, upload_files=True)

            success = result["success"]
            assert success


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_file_upload_without_session(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    app = web.Application()
    app.router.add_route(
        "POST",
        "/",
        make_upload_handler(
            expected_map=file_upload_mutation_1_map,
            expected_operations=file_upload_mutation_1_operations,
            expected_contents=[file_1_content],
        ),
    )
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    def test_code():
        transport = HTTPXAsyncTransport(url=url, timeout=10)

        with TemporaryFile(file_1_content) as test_file:

            client = Client(transport=transport)

            query = gql(file_upload_mutation_1)

            file_path = test_file.filename

            query.variable_values = {"file": FileVar(file_path), "other_var": 42}

            result = client.execute(query, upload_files=True)

            success = result["success"]

            assert success

    await run_sync_test(server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_binary_file_upload(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    # This is a sample binary file content containing all possible byte values
    binary_file_content = bytes(range(0, 256))

    app = web.Application()
    app.router.add_route(
        "POST",
        "/",
        make_upload_handler(
            binary=True,
            expected_contents=[binary_file_content],
            expected_map=file_upload_mutation_1_map,
            expected_operations=file_upload_mutation_1_operations,
        ),
    )
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url, timeout=10)

    with TemporaryFile(binary_file_content) as test_file:

        async with Client(transport=transport) as session:

            query = gql(file_upload_mutation_1)

            file_path = test_file.filename

            query.variable_values = {"file": FileVar(file_path), "other_var": 42}

            # Execute query asynchronously
            result = await session.execute(query, upload_files=True)

            success = result["success"]

            assert success


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_file_upload_two_files(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    file_upload_mutation_2 = """
    mutation($file1: Upload!, $file2: Upload!) {
      uploadFile(input:{file1:$file, file2:$file}) {
        success
      }
    }
    """

    file_upload_mutation_2_operations = (
        '{"query": "mutation ($file1: Upload!, $file2: Upload!) {\\n  '
        'uploadFile(input: {file1: $file, file2: $file}) {\\n    success\\n  }\\n}", '
        '"variables": {"file1": null, "file2": null}}'
    )

    file_upload_mutation_2_map = '{"0": ["variables.file1"], "1": ["variables.file2"]}'

    file_2_content = """
    This is a second test file
    This file will also be sent in the GraphQL mutation
    """

    app = web.Application()
    app.router.add_route(
        "POST",
        "/",
        make_upload_handler(
            nb_files=2,
            expected_map=file_upload_mutation_2_map,
            expected_operations=file_upload_mutation_2_operations,
            expected_contents=[file_1_content, file_2_content],
        ),
    )
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url, timeout=10)

    with TemporaryFile(file_1_content) as test_file_1:
        with TemporaryFile(file_2_content) as test_file_2:

            async with Client(transport=transport) as session:

                query = gql(file_upload_mutation_2)

                file_path_1 = test_file_1.filename
                file_path_2 = test_file_2.filename

                query.variable_values = {
                    "file1": FileVar(file_path_1),
                    "file2": FileVar(file_path_2),
                }

                result = await session.execute(query, upload_files=True)

                success = result["success"]
                assert success


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_file_upload_list_of_two_files(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    file_upload_mutation_3 = """
    mutation($files: [Upload!]!) {
      uploadFiles(input:{files:$files}) {
        success
      }
    }
    """

    file_upload_mutation_3_operations = (
        '{"query": "mutation ($files: [Upload!]!) {\\n  uploadFiles'
        "(input: {files: $files})"
        ' {\\n    success\\n  }\\n}", "variables": {"files": [null, null]}}'
    )

    file_upload_mutation_3_map = (
        '{"0": ["variables.files.0"], "1": ["variables.files.1"]}'
    )

    file_2_content = """
    This is a second test file
    This file will also be sent in the GraphQL mutation
    """

    app = web.Application()
    app.router.add_route(
        "POST",
        "/",
        make_upload_handler(
            nb_files=2,
            expected_map=file_upload_mutation_3_map,
            expected_operations=file_upload_mutation_3_operations,
            expected_contents=[file_1_content, file_2_content],
        ),
    )
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url, timeout=10)

    with TemporaryFile(file_1_content) as test_file_1:
        with TemporaryFile(file_2_content) as test_file_2:

            async with Client(transport=transport) as session:

                query = gql(file_upload_mutation_3)

                file_path_1 = test_file_1.filename
                file_path_2 = test_file_2.filename

                query.variable_values = {
                    "files": [
                        FileVar(file_path_1),
                        FileVar(file_path_2),
                    ],
                }

                # Execute query asynchronously
                result = await session.execute(query, upload_files=True)

                success = result["success"]
                assert success


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_using_cli(aiohttp_server, monkeypatch, capsys):
    from aiohttp import web

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    parser = get_parser(with_examples=True)
    args = parser.parse_args([url, "--verbose"])

    # Monkeypatching sys.stdin to simulate getting the query
    # via the standard input
    monkeypatch.setattr("sys.stdin", io.StringIO(query1_str))

    exit_code = await main(args)

    assert exit_code == 0

    # Check that the result has been printed on stdout
    captured = capsys.readouterr()
    captured_out = str(captured.out).strip()

    expected_answer = json.loads(query1_server_answer_data)
    print(f"Captured: {captured_out}")
    received_answer = json.loads(captured_out)

    assert received_answer == expected_answer


@pytest.mark.aiohttp
@pytest.mark.asyncio
@pytest.mark.script_launch_mode("subprocess")
async def test_httpx_using_cli_ep(
    aiohttp_server, monkeypatch, script_runner, run_sync_test
):
    from aiohttp import web

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    def test_code():

        monkeypatch.setattr("sys.stdin", io.StringIO(query1_str))

        ret = script_runner.run(
            ["gql-cli", url, "--verbose"],
            stdin=io.StringIO(query1_str),
        )

        assert ret.success

        # Check that the result has been printed on stdout
        captured_out = str(ret.stdout).strip()

        expected_answer = json.loads(query1_server_answer_data)
        print(f"Captured: {captured_out}")
        received_answer = json.loads(captured_out)

        assert received_answer == expected_answer

    await run_sync_test(server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_using_cli_invalid_param(aiohttp_server, monkeypatch, capsys):
    from aiohttp import web

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    parser = get_parser(with_examples=True)
    args = parser.parse_args([url, "--variables", "invalid_param"])

    # Monkeypatching sys.stdin to simulate getting the query
    # via the standard input
    monkeypatch.setattr("sys.stdin", io.StringIO(query1_str))

    # Check that the exit_code is an error
    exit_code = await main(args)
    assert exit_code == 1

    # Check that the error has been printed on stdout
    captured = capsys.readouterr()
    captured_err = str(captured.err).strip()
    print(f"Captured: {captured_err}")

    expected_error = "Error: Invalid variable: invalid_param"

    assert expected_error in captured_err


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_using_cli_invalid_query(aiohttp_server, monkeypatch, capsys):
    from aiohttp import web

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    parser = get_parser(with_examples=True)
    args = parser.parse_args([url])

    # Send invalid query on standard input
    monkeypatch.setattr("sys.stdin", io.StringIO("BLAHBLAH"))

    exit_code = await main(args)

    assert exit_code == 1

    # Check that the error has been printed on stdout
    captured = capsys.readouterr()
    captured_err = str(captured.err).strip()
    print(f"Captured: {captured_err}")

    expected_error = "Syntax Error: Unexpected Name 'BLAHBLAH'"

    assert expected_error in captured_err


query1_server_answer_with_extensions = (
    f'{{"data":{query1_server_answer_data}, "extensions":{{"key1": "val1"}}}}'
)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_query_with_extensions(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_with_extensions, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:

        query = gql(query1_str)

        execution_result = await session.execute(query, get_execution_result=True)

        assert execution_result.extensions["key1"] == "val1"


@pytest.mark.aiohttp
@pytest.mark.asyncio
@pytest.mark.parametrize("verify_https", ["disabled", "cert_provided"])
async def test_httpx_query_https(ssl_aiohttp_server, verify_https):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await ssl_aiohttp_server(app)

    url = str(server.make_url("/"))

    assert url.startswith("https://")

    extra_args = {}

    if verify_https == "cert_provided":
        _, ssl_context = get_localhost_ssl_context_client()

        extra_args["verify"] = ssl_context
    elif verify_https == "disabled":
        extra_args["verify"] = False

    transport = HTTPXAsyncTransport(url=url, timeout=10, **extra_args)

    async with Client(transport=transport) as session:

        query = gql(query1_str)

        # Execute query asynchronously
        result = await session.execute(query)

        continents = result["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"


@pytest.mark.aiohttp
@pytest.mark.asyncio
@pytest.mark.parametrize("verify_https", ["explicitely_enabled", "default"])
async def test_httpx_query_https_self_cert_fail(ssl_aiohttp_server, verify_https):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await ssl_aiohttp_server(app)

    url = str(server.make_url("/"))

    assert url.startswith("https://")

    extra_args: Dict[str, Any] = {}

    if verify_https == "explicitely_enabled":
        extra_args["verify"] = True

    transport = HTTPXAsyncTransport(url=url, timeout=10, **extra_args)

    query = gql(query1_str)

    expected_error = "certificate verify failed: self-signed certificate"

    with pytest.raises(TransportConnectionFailed) as exc_info:
        async with Client(transport=transport) as session:
            await session.execute(query)

    assert expected_error in str(exc_info.value)

    with pytest.raises(TransportConnectionFailed) as exc_info:
        async with Client(transport=transport) as session:
            await session.execute_batch([query])

    assert expected_error in str(exc_info.value)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_error_fetching_schema(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    error_answer = """
{
    "errors": [
        {
            "errorType": "UnauthorizedException",
            "message": "Permission denied"
        }
    ]
}
"""

    async def handler(request):
        return web.Response(
            text=error_answer,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url, timeout=10)

    with pytest.raises(TransportQueryError) as exc_info:
        async with Client(transport=transport, fetch_schema_from_transport=True):
            pass

    expected_error = (
        "Error while fetching schema: "
        "{'errorType': 'UnauthorizedException', 'message': 'Permission denied'}"
    )

    assert expected_error in str(exc_info.value)
    assert transport.client is None


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_reconnecting_session(aiohttp_server):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url, timeout=10)

    client = Client(transport=transport)

    session = await client.connect_async(reconnecting=True)

    query = gql(query1_str)

    # Execute query asynchronously
    result = await session.execute(query)

    continents = result["continents"]

    africa = continents[0]

    assert africa["code"] == "AF"

    await client.close_async()


@pytest.mark.aiohttp
@pytest.mark.asyncio
@pytest.mark.parametrize("retries", [False, lambda e: e])
async def test_httpx_reconnecting_session_retries(aiohttp_server, retries):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url, timeout=10)

    client = Client(transport=transport)

    session = await client.connect_async(
        reconnecting=True, retry_execute=retries, retry_connect=retries
    )

    assert session._execute_with_retries == session._execute_once
    assert session._connect_with_retries == session.transport.connect

    await client.close_async()


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_reconnecting_session_start_connecting_task_twice(
    aiohttp_server, caplog
):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(url=url, timeout=10)

    client = Client(transport=transport)

    session = await client.connect_async(reconnecting=True)

    await session.start_connecting_task()

    print(f"Captured log: {caplog.text}")

    expected_warning = "connect task already started!"
    assert expected_warning in caplog.text

    await client.close_async()


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_json_serializer(aiohttp_server, caplog):
    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):

        request_text = await request.text()
        print(f"Received on backend: {request_text}")

        return web.Response(
            text=query1_server_answer,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    transport = HTTPXAsyncTransport(
        url=url,
        timeout=10,
        json_serialize=lambda e: json.dumps(e, separators=(",", ":")),
    )

    async with Client(transport=transport) as session:

        query = gql(query1_str)

        # Execute query asynchronously
        result = await session.execute(query)

        continents = result["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"

    # Checking that there is no space after the colon in the log
    expected_log = '"query":"query getContinents'
    assert expected_log in caplog.text


query_float_str = """
    query getPi {
      pi
    }
"""

query_float_server_answer_data = '{"pi": 3.141592653589793238462643383279502884197}'

query_float_server_answer = f'{{"data":{query_float_server_answer_data}}}'


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_json_deserializer(aiohttp_server):
    from decimal import Decimal
    from functools import partial

    from aiohttp import web

    from gql.transport.httpx import HTTPXAsyncTransport

    async def handler(request):
        return web.Response(
            text=query_float_server_answer,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    json_loads = partial(json.loads, parse_float=Decimal)

    transport = HTTPXAsyncTransport(
        url=url,
        timeout=10,
        json_deserialize=json_loads,
    )

    async with Client(transport=transport) as session:

        query = gql(query_float_str)

        # Execute query asynchronously
        result = await session.execute(query)

        pi = result["pi"]

        assert pi == Decimal("3.141592653589793238462643383279502884197")
