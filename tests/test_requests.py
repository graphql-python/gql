import pytest

from gql import Client, gql
from gql.transport.exceptions import (
    TransportAlreadyConnected,
    TransportClosed,
    TransportProtocolError,
    TransportQueryError,
    TransportServerError,
)
from tests.conftest import TemporaryFile

# Marking all tests in this file with the requests marker
pytestmark = pytest.mark.requests

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
async def test_requests_query(event_loop, aiohttp_server, run_sync_test):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        sample_transport = RequestsHTTPTransport(url=url)

        with Client(transport=sample_transport,) as session:

            query = gql(query1_str)

            # Execute query synchronously
            result = session.execute(query)

            continents = result["continents"]

            africa = continents[0]

            assert africa["code"] == "AF"

    await run_sync_test(event_loop, server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_cookies(event_loop, aiohttp_server, run_sync_test):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        assert "COOKIE" in request.headers
        assert "cookie1=val1" == request.headers["COOKIE"]

        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        sample_transport = RequestsHTTPTransport(url=url, cookies={"cookie1": "val1"})

        with Client(transport=sample_transport,) as session:

            query = gql(query1_str)

            # Execute query synchronously
            result = session.execute(query)

            continents = result["continents"]

            africa = continents[0]

            assert africa["code"] == "AF"

    await run_sync_test(event_loop, server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_error_code_401(event_loop, aiohttp_server, run_sync_test):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

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

    url = server.make_url("/")

    def test_code():
        sample_transport = RequestsHTTPTransport(url=url)

        with Client(transport=sample_transport,) as session:

            query = gql(query1_str)

            with pytest.raises(TransportServerError) as exc_info:
                session.execute(query)

            assert "401 Client Error: Unauthorized" in str(exc_info.value)

    await run_sync_test(event_loop, server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_error_code_500(event_loop, aiohttp_server, run_sync_test):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        # Will generate http error code 500
        raise Exception("Server error")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        sample_transport = RequestsHTTPTransport(url=url)

        with Client(transport=sample_transport,) as session:

            query = gql(query1_str)

            with pytest.raises(TransportServerError):
                session.execute(query)

    await run_sync_test(event_loop, server, test_code)


query1_server_error_answer = '{"errors": ["Error 1", "Error 2"]}'


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_error_code(event_loop, aiohttp_server, run_sync_test):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        return web.Response(
            text=query1_server_error_answer, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        sample_transport = RequestsHTTPTransport(url=url)

        with Client(transport=sample_transport,) as session:

            query = gql(query1_str)

            with pytest.raises(TransportQueryError):
                session.execute(query)

    await run_sync_test(event_loop, server, test_code)


invalid_protocol_responses = [
    "{}",
    "qlsjfqsdlkj",
    '{"not_data_or_errors": 35}',
]


@pytest.mark.aiohttp
@pytest.mark.asyncio
@pytest.mark.parametrize("response", invalid_protocol_responses)
async def test_requests_invalid_protocol(
    event_loop, aiohttp_server, response, run_sync_test
):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        return web.Response(text=response, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        sample_transport = RequestsHTTPTransport(url=url)

        with Client(transport=sample_transport,) as session:

            query = gql(query1_str)

            with pytest.raises(TransportProtocolError):
                session.execute(query)

    await run_sync_test(event_loop, server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_cannot_connect_twice(event_loop, aiohttp_server, run_sync_test):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        sample_transport = RequestsHTTPTransport(url=url)

        with Client(transport=sample_transport,) as session:

            with pytest.raises(TransportAlreadyConnected):
                session.transport.connect()

    await run_sync_test(event_loop, server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_cannot_execute_if_not_connected(
    event_loop, aiohttp_server, run_sync_test
):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        sample_transport = RequestsHTTPTransport(url=url)

        query = gql(query1_str)

        with pytest.raises(TransportClosed):
            sample_transport.execute(query)

    await run_sync_test(event_loop, server, test_code)


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
async def test_requests_query_with_extensions(
    event_loop, aiohttp_server, run_sync_test
):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_with_extensions, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        sample_transport = RequestsHTTPTransport(url=url)

        with Client(transport=sample_transport,) as session:

            query = gql(query1_str)

            execution_result = session.execute(query, get_execution_result=True)

            assert execution_result.extensions["key1"] == "val1"

    await run_sync_test(event_loop, server, test_code)


file_upload_server_answer = '{"data":{"success":true}}'

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
async def test_requests_file_upload(event_loop, aiohttp_server, run_sync_test):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def single_upload_handler(request):
        from aiohttp import web

        reader = await request.multipart()

        field_0 = await reader.next()
        assert field_0.name == "operations"
        field_0_text = await field_0.text()
        assert field_0_text == file_upload_mutation_1_operations

        field_1 = await reader.next()
        assert field_1.name == "map"
        field_1_text = await field_1.text()
        assert field_1_text == file_upload_mutation_1_map

        field_2 = await reader.next()
        assert field_2.name == "0"
        field_2_text = await field_2.text()
        assert field_2_text == file_1_content

        field_3 = await reader.next()
        assert field_3 is None

        return web.Response(
            text=file_upload_server_answer, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", single_upload_handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        sample_transport = RequestsHTTPTransport(url=url)

        with TemporaryFile(file_1_content) as test_file:
            with Client(transport=sample_transport) as session:
                query = gql(file_upload_mutation_1)

                file_path = test_file.filename

                with open(file_path, "rb") as f:

                    params = {"file": f, "other_var": 42}
                    execution_result = session._execute(
                        query, variable_values=params, upload_files=True
                    )

                    assert execution_result.data["success"]

    await run_sync_test(event_loop, server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_file_upload_additional_headers(
    event_loop, aiohttp_server, run_sync_test
):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def single_upload_handler(request):
        from aiohttp import web

        assert request.headers["X-Auth"] == "foobar"

        reader = await request.multipart()

        field_0 = await reader.next()
        assert field_0.name == "operations"
        field_0_text = await field_0.text()
        assert field_0_text == file_upload_mutation_1_operations

        field_1 = await reader.next()
        assert field_1.name == "map"
        field_1_text = await field_1.text()
        assert field_1_text == file_upload_mutation_1_map

        field_2 = await reader.next()
        assert field_2.name == "0"
        field_2_text = await field_2.text()
        assert field_2_text == file_1_content

        field_3 = await reader.next()
        assert field_3 is None

        return web.Response(
            text=file_upload_server_answer, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", single_upload_handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        sample_transport = RequestsHTTPTransport(url=url, headers={"X-Auth": "foobar"})

        with TemporaryFile(file_1_content) as test_file:
            with Client(transport=sample_transport) as session:
                query = gql(file_upload_mutation_1)

                file_path = test_file.filename

                with open(file_path, "rb") as f:

                    params = {"file": f, "other_var": 42}
                    execution_result = session._execute(
                        query, variable_values=params, upload_files=True
                    )

                    assert execution_result.data["success"]

    await run_sync_test(event_loop, server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_binary_file_upload(event_loop, aiohttp_server, run_sync_test):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    # This is a sample binary file content containing all possible byte values
    binary_file_content = bytes(range(0, 256))

    async def binary_upload_handler(request):

        from aiohttp import web

        reader = await request.multipart()

        field_0 = await reader.next()
        assert field_0.name == "operations"
        field_0_text = await field_0.text()
        assert field_0_text == file_upload_mutation_1_operations

        field_1 = await reader.next()
        assert field_1.name == "map"
        field_1_text = await field_1.text()
        assert field_1_text == file_upload_mutation_1_map

        field_2 = await reader.next()
        assert field_2.name == "0"
        field_2_binary = await field_2.read()
        assert field_2_binary == binary_file_content

        field_3 = await reader.next()
        assert field_3 is None

        return web.Response(
            text=file_upload_server_answer, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", binary_upload_handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = RequestsHTTPTransport(url=url)

    def test_code():
        with TemporaryFile(binary_file_content) as test_file:
            with Client(transport=sample_transport,) as session:

                query = gql(file_upload_mutation_1)

                file_path = test_file.filename

                with open(file_path, "rb") as f:

                    params = {"file": f, "other_var": 42}

                    execution_result = session._execute(
                        query, variable_values=params, upload_files=True
                    )

                    assert execution_result.data["success"]

    await run_sync_test(event_loop, server, test_code)


file_upload_mutation_2_operations = (
    '{"query": "mutation ($file1: Upload!, $file2: Upload!) {\\n  '
    'uploadFile(input: {file1: $file, file2: $file}) {\\n    success\\n  }\\n}", '
    '"variables": {"file1": null, "file2": null}}'
)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_file_upload_two_files(
    event_loop, aiohttp_server, run_sync_test
):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    file_upload_mutation_2 = """
    mutation($file1: Upload!, $file2: Upload!) {
      uploadFile(input:{file1:$file, file2:$file}) {
        success
      }
    }
    """

    file_upload_mutation_2_map = '{"0": ["variables.file1"], "1": ["variables.file2"]}'

    file_2_content = """
    This is a second test file
    This file will also be sent in the GraphQL mutation
    """

    async def handler(request):

        reader = await request.multipart()

        field_0 = await reader.next()
        assert field_0.name == "operations"
        field_0_text = await field_0.text()
        assert field_0_text == file_upload_mutation_2_operations

        field_1 = await reader.next()
        assert field_1.name == "map"
        field_1_text = await field_1.text()
        assert field_1_text == file_upload_mutation_2_map

        field_2 = await reader.next()
        assert field_2.name == "0"
        field_2_text = await field_2.text()
        assert field_2_text == file_1_content

        field_3 = await reader.next()
        assert field_3.name == "1"
        field_3_text = await field_3.text()
        assert field_3_text == file_2_content

        field_4 = await reader.next()
        assert field_4 is None

        return web.Response(
            text=file_upload_server_answer, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        sample_transport = RequestsHTTPTransport(url=url)

        with TemporaryFile(file_1_content) as test_file_1:
            with TemporaryFile(file_2_content) as test_file_2:

                with Client(transport=sample_transport,) as session:

                    query = gql(file_upload_mutation_2)

                    file_path_1 = test_file_1.filename
                    file_path_2 = test_file_2.filename

                    f1 = open(file_path_1, "rb")
                    f2 = open(file_path_2, "rb")

                    params = {
                        "file1": f1,
                        "file2": f2,
                    }

                    execution_result = session._execute(
                        query, variable_values=params, upload_files=True
                    )

                    assert execution_result.data["success"]

                    f1.close()
                    f2.close()

    await run_sync_test(event_loop, server, test_code)


file_upload_mutation_3_operations = (
    '{"query": "mutation ($files: [Upload!]!) {\\n  uploadFiles(input: {files: $files})'
    ' {\\n    success\\n  }\\n}", "variables": {"files": [null, null]}}'
)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_file_upload_list_of_two_files(
    event_loop, aiohttp_server, run_sync_test
):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    file_upload_mutation_3 = """
    mutation($files: [Upload!]!) {
      uploadFiles(input:{files:$files}) {
        success
      }
    }
    """

    file_upload_mutation_3_map = (
        '{"0": ["variables.files.0"], "1": ["variables.files.1"]}'
    )

    file_2_content = """
    This is a second test file
    This file will also be sent in the GraphQL mutation
    """

    async def handler(request):

        reader = await request.multipart()

        field_0 = await reader.next()
        assert field_0.name == "operations"
        field_0_text = await field_0.text()
        assert field_0_text == file_upload_mutation_3_operations

        field_1 = await reader.next()
        assert field_1.name == "map"
        field_1_text = await field_1.text()
        assert field_1_text == file_upload_mutation_3_map

        field_2 = await reader.next()
        assert field_2.name == "0"
        field_2_text = await field_2.text()
        assert field_2_text == file_1_content

        field_3 = await reader.next()
        assert field_3.name == "1"
        field_3_text = await field_3.text()
        assert field_3_text == file_2_content

        field_4 = await reader.next()
        assert field_4 is None

        return web.Response(
            text=file_upload_server_answer, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        sample_transport = RequestsHTTPTransport(url=url)

        with TemporaryFile(file_1_content) as test_file_1:
            with TemporaryFile(file_2_content) as test_file_2:
                with Client(transport=sample_transport,) as session:

                    query = gql(file_upload_mutation_3)

                    file_path_1 = test_file_1.filename
                    file_path_2 = test_file_2.filename

                    f1 = open(file_path_1, "rb")
                    f2 = open(file_path_2, "rb")

                    params = {"files": [f1, f2]}

                    execution_result = session._execute(
                        query, variable_values=params, upload_files=True
                    )

                    assert execution_result.data["success"]

                    f1.close()
                    f2.close()

    await run_sync_test(event_loop, server, test_code)
