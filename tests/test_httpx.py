import os
from typing import Any, Dict, Mapping

import pytest

from gql import Client, FileVar, gql
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

# Marking all tests in this file with the httpx marker
pytestmark = pytest.mark.httpx

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


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_query(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

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

    def test_code():
        transport = HTTPXTransport(url=url)

        with Client(transport=transport) as session:

            query = gql(query1_str)

            # Execute query synchronously
            result = session.execute(query)

            continents = result["continents"]

            africa = continents[0]

            assert africa["code"] == "AF"

            # Checking response headers are saved in the transport
            assert hasattr(transport, "response_headers")
            assert isinstance(transport.response_headers, Mapping)
            assert transport.response_headers["dummy"] == "test1234"

    await run_sync_test(server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
@pytest.mark.parametrize("verify_https", ["disabled", "cert_provided"])
async def test_httpx_query_https(ssl_aiohttp_server, run_sync_test, verify_https):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer,
            content_type="application/json",
            headers={"dummy": "test1234"},
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await ssl_aiohttp_server(app)

    url = str(server.make_url("/"))

    assert str(url).startswith("https://")

    def test_code():
        extra_args = {}

        if verify_https == "cert_provided":
            _, ssl_context = get_localhost_ssl_context_client()

            extra_args["verify"] = ssl_context
        elif verify_https == "disabled":
            extra_args["verify"] = False

        transport = HTTPXTransport(
            url=url,
            **extra_args,
        )

        with Client(transport=transport) as session:

            query = gql(query1_str)

            # Execute query synchronously
            result = session.execute(query)

            continents = result["continents"]

            africa = continents[0]

            assert africa["code"] == "AF"

            # Checking response headers are saved in the transport
            assert hasattr(transport, "response_headers")
            assert isinstance(transport.response_headers, Mapping)
            assert transport.response_headers["dummy"] == "test1234"

    await run_sync_test(server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
@pytest.mark.parametrize("verify_https", ["explicitely_enabled", "default"])
async def test_httpx_query_https_self_cert_fail(
    ssl_aiohttp_server, run_sync_test, verify_https
):
    """By default, we should verify the ssl certificate"""
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer,
            content_type="application/json",
            headers={"dummy": "test1234"},
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await ssl_aiohttp_server(app)

    url = str(server.make_url("/"))

    assert str(url).startswith("https://")

    def test_code():
        extra_args: Dict[str, Any] = {}

        if verify_https == "explicitely_enabled":
            extra_args["verify"] = True

        transport = HTTPXTransport(
            url=url,
            **extra_args,
        )

        query = gql(query1_str)

        expected_error = "certificate verify failed: self-signed certificate"

        with pytest.raises(TransportConnectionFailed) as exc_info:
            with Client(transport=transport) as session:
                session.execute(query)

        assert expected_error in str(exc_info.value)

        with pytest.raises(TransportConnectionFailed) as exc_info:
            with Client(transport=transport) as session:
                session.execute_batch([query])

        assert expected_error in str(exc_info.value)

    await run_sync_test(server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_cookies(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

    async def handler(request):
        assert "COOKIE" in request.headers
        assert "cookie1=val1" == request.headers["COOKIE"]

        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    def test_code():
        transport = HTTPXTransport(url=url, cookies={"cookie1": "val1"})

        with Client(transport=transport) as session:

            query = gql(query1_str)

            # Execute query synchronously
            result = session.execute(query)

            continents = result["continents"]

            africa = continents[0]

            assert africa["code"] == "AF"

    await run_sync_test(server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_error_code_401(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

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

    def test_code():
        transport = HTTPXTransport(url=url)

        with Client(transport=transport) as session:

            query = gql(query1_str)

            with pytest.raises(TransportServerError) as exc_info:
                session.execute(query)

            assert "Client error '401 Unauthorized'" in str(exc_info.value)

    await run_sync_test(server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_error_code_429(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

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

    def test_code():
        transport = HTTPXTransport(url=url)

        with Client(transport=transport) as session:

            query = gql(query1_str)

            with pytest.raises(TransportServerError) as exc_info:
                session.execute(query)

            assert "429, message='Too Many Requests'" in str(exc_info.value)

        # Checking response headers are saved in the transport
        assert hasattr(transport, "response_headers")
        assert isinstance(transport.response_headers, Mapping)
        assert transport.response_headers["Retry-After"] == "3600"


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_error_code_500(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

    async def handler(request):
        # Will generate http error code 500
        raise Exception("Server error")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    def test_code():
        transport = HTTPXTransport(url=url)

        with Client(transport=transport) as session:

            query = gql(query1_str)

            with pytest.raises(TransportServerError):
                session.execute(query)

    await run_sync_test(server, test_code)


query1_server_error_answer = '{"errors": ["Error 1", "Error 2"]}'


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_error_code(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

    async def handler(request):
        return web.Response(
            text=query1_server_error_answer, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    def test_code():
        transport = HTTPXTransport(url=url)

        with Client(transport=transport) as session:

            query = gql(query1_str)

            with pytest.raises(TransportQueryError):
                session.execute(query)

    await run_sync_test(server, test_code)


invalid_protocol_responses = [
    "{}",
    "qlsjfqsdlkj",
    '{"not_data_or_errors": 35}',
    "",
]


@pytest.mark.aiohttp
@pytest.mark.asyncio
@pytest.mark.parametrize("response", invalid_protocol_responses)
async def test_httpx_invalid_protocol(aiohttp_server, response, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

    async def handler(request):
        return web.Response(text=response, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    def test_code():
        transport = HTTPXTransport(url=url)

        with Client(transport=transport) as session:

            query = gql(query1_str)

            with pytest.raises(TransportProtocolError):
                session.execute(query)

    await run_sync_test(server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_cannot_connect_twice(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    def test_code():
        transport = HTTPXTransport(url=url)

        with Client(transport=transport) as session:

            with pytest.raises(TransportAlreadyConnected):
                session.transport.connect()

    await run_sync_test(server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_cannot_execute_if_not_connected(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    def test_code():
        transport = HTTPXTransport(url=url)

        query = gql(query1_str)

        with pytest.raises(TransportClosed):
            transport.execute(query)

    await run_sync_test(server, test_code)


query1_server_answer_with_extensions = (
    '{"data":{"continents":['
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
    '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
    '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
    '{"code":"SA","name":"South America"}]},'
    '"extensions": {"key1": "val1"}'
    "}"
)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_query_with_extensions(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_with_extensions, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    def test_code():
        transport = HTTPXTransport(url=url)

        with Client(transport=transport) as session:

            query = gql(query1_str)

            execution_result = session.execute(query, get_execution_result=True)

            assert execution_result.extensions["key1"] == "val1"

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
async def test_httpx_file_upload(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

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
        transport = HTTPXTransport(url=url)

        with TemporaryFile(file_1_content) as test_file:
            with Client(transport=transport) as session:
                query = gql(file_upload_mutation_1)

                file_path = test_file.filename

                # Using an opened file
                with open(file_path, "rb") as f:

                    query.variable_values = {"file": f, "other_var": 42}
                    with pytest.warns(
                        DeprecationWarning,
                        match="Not using FileVar for file upload is deprecated",
                    ):
                        execution_result = session.execute(query, upload_files=True)

                    assert execution_result["success"]

                # Using an opened file inside a FileVar object
                with open(file_path, "rb") as f:

                    query.variable_values = {"file": FileVar(f), "other_var": 42}
                    execution_result = session.execute(query, upload_files=True)

                    assert execution_result["success"]

                # Using an filename string inside a FileVar object
                query.variable_values = {
                    "file": FileVar(file_path),
                    "other_var": 42,
                }
                execution_result = session.execute(query, upload_files=True)

                assert execution_result["success"]

    await run_sync_test(server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_file_upload_with_content_type(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

    app = web.Application()
    app.router.add_route(
        "POST",
        "/",
        make_upload_handler(
            file_headers=[{"Content-Type": "application/pdf"}],
            expected_map=file_upload_mutation_1_map,
            expected_operations=file_upload_mutation_1_operations,
            expected_contents=[file_1_content],
        ),
    )
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    def test_code():
        transport = HTTPXTransport(url=url)

        with TemporaryFile(file_1_content) as test_file:
            with Client(transport=transport) as session:
                query = gql(file_upload_mutation_1)

                file_path = test_file.filename

                # Using an opened file
                with open(file_path, "rb") as f:

                    # Setting the content_type
                    f.content_type = "application/pdf"  # type: ignore

                    query.variable_values = {"file": f, "other_var": 42}
                    with pytest.warns(
                        DeprecationWarning,
                        match="Not using FileVar for file upload is deprecated",
                    ):
                        execution_result = session.execute(query, upload_files=True)

                    assert execution_result["success"]

                # Using FileVar
                query.variable_values = {
                    "file": FileVar(file_path, content_type="application/pdf"),
                    "other_var": 42,
                }
                execution_result = session.execute(query, upload_files=True)

                assert execution_result["success"]

    await run_sync_test(server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_file_upload_default_filename_is_basename(
    aiohttp_server, run_sync_test
):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

    app = web.Application()

    with TemporaryFile(file_1_content) as test_file:
        file_path = test_file.filename
        file_basename = os.path.basename(file_path)

        app.router.add_route(
            "POST",
            "/",
            make_upload_handler(
                filenames=[file_basename],
                expected_map=file_upload_mutation_1_map,
                expected_operations=file_upload_mutation_1_operations,
                expected_contents=[file_1_content],
            ),
        )
        server = await aiohttp_server(app)

        url = str(server.make_url("/"))

        def test_code():
            transport = HTTPXTransport(url=url)

            with Client(transport=transport) as session:
                query = gql(file_upload_mutation_1)

                # Using FileVar
                query.variable_values = {
                    "file": FileVar(file_path),
                    "other_var": 42,
                }
                execution_result = session.execute(query, upload_files=True)

                assert execution_result["success"]

        await run_sync_test(server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_file_upload_additional_headers(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

    app = web.Application()
    app.router.add_route(
        "POST",
        "/",
        make_upload_handler(
            request_headers={"X-Auth": "foobar"},
            expected_map=file_upload_mutation_1_map,
            expected_operations=file_upload_mutation_1_operations,
            expected_contents=[file_1_content],
        ),
    )
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    def test_code():
        transport = HTTPXTransport(url=url, headers={"X-Auth": "foobar"})

        with TemporaryFile(file_1_content) as test_file:
            with Client(transport=transport) as session:
                query = gql(file_upload_mutation_1)

                file_path = test_file.filename

                query.variable_values = {"file": FileVar(file_path), "other_var": 42}
                execution_result = session.execute(query, upload_files=True)

                assert execution_result["success"]

    await run_sync_test(server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_binary_file_upload(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

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

    transport = HTTPXTransport(url=url)

    def test_code():
        with TemporaryFile(binary_file_content) as test_file:
            with Client(transport=transport) as session:

                query = gql(file_upload_mutation_1)

                file_path = test_file.filename

                query.variable_values = {"file": FileVar(file_path), "other_var": 42}

                execution_result = session.execute(query, upload_files=True)

                assert execution_result["success"]

    await run_sync_test(server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_file_upload_two_files(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

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

    def test_code():
        transport = HTTPXTransport(url=url)

        with TemporaryFile(file_1_content) as test_file_1:
            with TemporaryFile(file_2_content) as test_file_2:

                with Client(transport=transport) as session:

                    query = gql(file_upload_mutation_2)

                    file_path_1 = test_file_1.filename
                    file_path_2 = test_file_2.filename

                    query.variable_values = {
                        "file1": FileVar(file_path_1),
                        "file2": FileVar(file_path_2),
                    }

                    execution_result = session.execute(query, upload_files=True)

                    assert execution_result["success"]

    await run_sync_test(server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_file_upload_list_of_two_files(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

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

    def test_code():
        transport = HTTPXTransport(url=url)

        with TemporaryFile(file_1_content) as test_file_1:
            with TemporaryFile(file_2_content) as test_file_2:
                with Client(transport=transport) as session:

                    query = gql(file_upload_mutation_3)

                    file_path_1 = test_file_1.filename
                    file_path_2 = test_file_2.filename

                    query.variable_values = {
                        "files": [
                            FileVar(file_path_1),
                            FileVar(file_path_2),
                        ],
                    }

                    execution_result = session.execute(query, upload_files=True)

                    assert execution_result["success"]

    await run_sync_test(server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_httpx_error_fetching_schema(aiohttp_server, run_sync_test):
    from aiohttp import web

    from gql.transport.httpx import HTTPXTransport

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

    def test_code():
        transport = HTTPXTransport(url=url)

        with pytest.raises(TransportQueryError) as exc_info:
            with Client(transport=transport, fetch_schema_from_transport=True):
                pass

        expected_error = (
            "Error while fetching schema: "
            "{'errorType': 'UnauthorizedException', 'message': 'Permission denied'}"
        )

        assert expected_error in str(exc_info.value)
        assert transport.client is None

    await run_sync_test(server, test_code)
