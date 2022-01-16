import io
import json

import pytest

from gql import Client, gql
from gql.cli import get_parser, main
from gql.transport.exceptions import (
    TransportAlreadyConnected,
    TransportClosed,
    TransportProtocolError,
    TransportQueryError,
    TransportServerError,
)

from .conftest import TemporaryFile

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

# Marking all tests in this file with the aiohttp marker
pytestmark = pytest.mark.aiohttp


@pytest.mark.asyncio
async def test_aiohttp_query(event_loop, aiohttp_server):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url, timeout=10)

    async with Client(transport=sample_transport,) as session:

        query = gql(query1_str)

        # Execute query asynchronously
        result = await session.execute(query)

        continents = result["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"


@pytest.mark.asyncio
async def test_aiohttp_ignore_backend_content_type(event_loop, aiohttp_server):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="text/plain")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url, timeout=10)

    async with Client(transport=sample_transport,) as session:

        query = gql(query1_str)

        result = await session.execute(query)

        continents = result["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"


@pytest.mark.asyncio
async def test_aiohttp_cookies(event_loop, aiohttp_server):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        assert "COOKIE" in request.headers
        assert "cookie1=val1" == request.headers["COOKIE"]

        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url, cookies={"cookie1": "val1"})

    async with Client(transport=sample_transport,) as session:

        query = gql(query1_str)

        # Execute query asynchronously
        result = await session.execute(query)

        continents = result["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"


@pytest.mark.asyncio
async def test_aiohttp_error_code_401(event_loop, aiohttp_server):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

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

    sample_transport = AIOHTTPTransport(url=url)

    async with Client(transport=sample_transport,) as session:

        query = gql(query1_str)

        with pytest.raises(TransportServerError) as exc_info:
            await session.execute(query)

        assert "401, message='Unauthorized'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_aiohttp_error_code_500(event_loop, aiohttp_server):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        # Will generate http error code 500
        raise Exception("Server error")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url)

    async with Client(transport=sample_transport,) as session:

        query = gql(query1_str)

        with pytest.raises(TransportServerError) as exc_info:
            await session.execute(query)

        assert "500, message='Internal Server Error'" in str(exc_info.value)


query1_server_error_answer = '{"errors": ["Error 1", "Error 2"]}'


@pytest.mark.asyncio
async def test_aiohttp_error_code(event_loop, aiohttp_server):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        return web.Response(
            text=query1_server_error_answer, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url)

    async with Client(transport=sample_transport,) as session:

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
]


@pytest.mark.asyncio
@pytest.mark.parametrize("param", invalid_protocol_responses)
async def test_aiohttp_invalid_protocol(event_loop, aiohttp_server, param):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

    response = param["response"]

    async def handler(request):
        return web.Response(text=response, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url)

    async with Client(transport=sample_transport,) as session:

        query = gql(query1_str)

        with pytest.raises(TransportProtocolError) as exc_info:
            await session.execute(query)

        assert param["expected_exception"] in str(exc_info.value)


@pytest.mark.asyncio
async def test_aiohttp_subscribe_not_supported(event_loop, aiohttp_server):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        return web.Response(text="does not matter", content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url)

    async with Client(transport=sample_transport,) as session:

        query = gql(query1_str)

        with pytest.raises(NotImplementedError):
            async for result in session.subscribe(query):
                pass


@pytest.mark.asyncio
async def test_aiohttp_cannot_connect_twice(event_loop, aiohttp_server):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url, timeout=10)

    async with Client(transport=sample_transport,) as session:

        with pytest.raises(TransportAlreadyConnected):
            await session.transport.connect()


@pytest.mark.asyncio
async def test_aiohttp_cannot_execute_if_not_connected(event_loop, aiohttp_server):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url, timeout=10)

    query = gql(query1_str)

    with pytest.raises(TransportClosed):
        await sample_transport.execute(query)


@pytest.mark.asyncio
async def test_aiohttp_extra_args(event_loop, aiohttp_server):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    # passing extra arguments to aiohttp.ClientSession
    from aiohttp import DummyCookieJar

    jar = DummyCookieJar()
    sample_transport = AIOHTTPTransport(
        url=url, timeout=10, client_session_args={"version": "1.1", "cookie_jar": jar}
    )

    async with Client(transport=sample_transport,) as session:

        query = gql(query1_str)

        # Passing extra arguments to the post method of aiohttp
        result = await session.execute(query, extra_args={"allow_redirects": False})

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


@pytest.mark.asyncio
async def test_aiohttp_query_variable_values(event_loop, aiohttp_server):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        return web.Response(text=query2_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url, timeout=10)

    async with Client(transport=sample_transport,) as session:

        params = {"code": "EU"}

        query = gql(query2_str)

        # Execute query asynchronously
        result = await session.execute(
            query, variable_values=params, operation_name="getEurope"
        )

        continent = result["continent"]

        assert continent["name"] == "Europe"


@pytest.mark.asyncio
async def test_aiohttp_execute_running_in_thread(
    event_loop, aiohttp_server, run_sync_test
):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        sample_transport = AIOHTTPTransport(url=url)

        client = Client(transport=sample_transport)

        query = gql(query1_str)

        client.execute(query)

    await run_sync_test(event_loop, server, test_code)


@pytest.mark.asyncio
async def test_aiohttp_subscribe_running_in_thread(
    event_loop, aiohttp_server, run_sync_test
):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        sample_transport = AIOHTTPTransport(url=url)

        client = Client(transport=sample_transport)

        query = gql(query1_str)

        # Note: subscriptions are not supported on the aiohttp transport
        # But we add this test in order to have 100% code coverage
        # It is to check that we will correctly set an event loop
        # in the subscribe function if there is none (in a Thread for example)
        # We cannot test this with the websockets transport because
        # the websockets transport will set an event loop in its init

        with pytest.raises(NotImplementedError):
            for result in client.subscribe(query):
                pass

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

    return web.Response(text=file_upload_server_answer, content_type="application/json")


@pytest.mark.asyncio
async def test_aiohttp_file_upload(event_loop, aiohttp_server):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

    app = web.Application()
    app.router.add_route("POST", "/", single_upload_handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url, timeout=10)

    with TemporaryFile(file_1_content) as test_file:

        async with Client(transport=sample_transport,) as session:

            query = gql(file_upload_mutation_1)

            file_path = test_file.filename

            with open(file_path, "rb") as f:

                params = {"file": f, "other_var": 42}

                # Execute query asynchronously
                result = await session.execute(
                    query, variable_values=params, upload_files=True
                )

            success = result["success"]

            assert success


@pytest.mark.asyncio
async def test_aiohttp_file_upload_without_session(
    event_loop, aiohttp_server, run_sync_test
):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

    app = web.Application()
    app.router.add_route("POST", "/", single_upload_handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        sample_transport = AIOHTTPTransport(url=url, timeout=10)

        with TemporaryFile(file_1_content) as test_file:

            client = Client(transport=sample_transport,)

            query = gql(file_upload_mutation_1)

            file_path = test_file.filename

            with open(file_path, "rb") as f:

                params = {"file": f, "other_var": 42}

                result = client.execute(
                    query, variable_values=params, upload_files=True
                )

                success = result["success"]

                assert success

    await run_sync_test(event_loop, server, test_code)


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

    return web.Response(text=file_upload_server_answer, content_type="application/json")


@pytest.mark.asyncio
async def test_aiohttp_binary_file_upload(event_loop, aiohttp_server):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

    app = web.Application()
    app.router.add_route("POST", "/", binary_upload_handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url, timeout=10)

    with TemporaryFile(binary_file_content) as test_file:

        async with Client(transport=sample_transport,) as session:

            query = gql(file_upload_mutation_1)

            file_path = test_file.filename

            with open(file_path, "rb") as f:

                params = {"file": f, "other_var": 42}

                # Execute query asynchronously
                result = await session.execute(
                    query, variable_values=params, upload_files=True
                )

            success = result["success"]

            assert success


@pytest.mark.asyncio
async def test_aiohttp_stream_reader_upload(event_loop, aiohttp_server):
    from aiohttp import web, ClientSession
    from gql.transport.aiohttp import AIOHTTPTransport

    async def binary_data_handler(request):
        return web.Response(
            body=binary_file_content, content_type="binary/octet-stream"
        )

    app = web.Application()
    app.router.add_route("POST", "/", binary_upload_handler)
    app.router.add_route("GET", "/binary_data", binary_data_handler)

    server = await aiohttp_server(app)

    url = server.make_url("/")
    binary_data_url = server.make_url("/binary_data")

    sample_transport = AIOHTTPTransport(url=url, timeout=10)

    async with Client(transport=sample_transport) as session:
        query = gql(file_upload_mutation_1)
        async with ClientSession() as client:
            async with client.get(binary_data_url) as resp:
                params = {"file": resp.content, "other_var": 42}

                # Execute query asynchronously
                result = await session.execute(
                    query, variable_values=params, upload_files=True
                )

    success = result["success"]

    assert success


@pytest.mark.asyncio
async def test_aiohttp_async_generator_upload(event_loop, aiohttp_server):
    import aiofiles
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

    app = web.Application()
    app.router.add_route("POST", "/", binary_upload_handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url, timeout=10)

    with TemporaryFile(binary_file_content) as test_file:

        async with Client(transport=sample_transport,) as session:

            query = gql(file_upload_mutation_1)

            file_path = test_file.filename

            async def file_sender(file_name):
                async with aiofiles.open(file_name, "rb") as f:
                    chunk = await f.read(64 * 1024)
                    while chunk:
                        yield chunk
                        chunk = await f.read(64 * 1024)

            params = {"file": file_sender(file_path), "other_var": 42}

            # Execute query asynchronously
            result = await session.execute(
                query, variable_values=params, upload_files=True
            )

            success = result["success"]

            assert success


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


@pytest.mark.asyncio
async def test_aiohttp_file_upload_two_files(event_loop, aiohttp_server):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

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

    sample_transport = AIOHTTPTransport(url=url, timeout=10)

    with TemporaryFile(file_1_content) as test_file_1:
        with TemporaryFile(file_2_content) as test_file_2:

            async with Client(transport=sample_transport,) as session:

                query = gql(file_upload_mutation_2)

                file_path_1 = test_file_1.filename
                file_path_2 = test_file_2.filename

                f1 = open(file_path_1, "rb")
                f2 = open(file_path_2, "rb")

                params = {
                    "file1": f1,
                    "file2": f2,
                }

                result = await session.execute(
                    query, variable_values=params, upload_files=True
                )

                f1.close()
                f2.close()

                success = result["success"]

                assert success


file_upload_mutation_3 = """
    mutation($files: [Upload!]!) {
      uploadFiles(input:{files:$files}) {
        success
      }
    }
"""

file_upload_mutation_3_operations = (
    '{"query": "mutation ($files: [Upload!]!) {\\n  uploadFiles(input: {files: $files})'
    ' {\\n    success\\n  }\\n}", "variables": {"files": [null, null]}}'
)

file_upload_mutation_3_map = '{"0": ["variables.files.0"], "1": ["variables.files.1"]}'


@pytest.mark.asyncio
async def test_aiohttp_file_upload_list_of_two_files(event_loop, aiohttp_server):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

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

    sample_transport = AIOHTTPTransport(url=url, timeout=10)

    with TemporaryFile(file_1_content) as test_file_1:
        with TemporaryFile(file_2_content) as test_file_2:

            async with Client(transport=sample_transport,) as session:

                query = gql(file_upload_mutation_3)

                file_path_1 = test_file_1.filename
                file_path_2 = test_file_2.filename

                f1 = open(file_path_1, "rb")
                f2 = open(file_path_2, "rb")

                params = {"files": [f1, f2]}

                # Execute query asynchronously
                result = await session.execute(
                    query, variable_values=params, upload_files=True
                )

                f1.close()
                f2.close()

                success = result["success"]

                assert success


@pytest.mark.asyncio
async def test_aiohttp_using_cli(event_loop, aiohttp_server, monkeypatch, capsys):
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


@pytest.mark.asyncio
async def test_aiohttp_using_cli_invalid_param(
    event_loop, aiohttp_server, monkeypatch, capsys
):
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


@pytest.mark.asyncio
async def test_aiohttp_using_cli_invalid_query(
    event_loop, aiohttp_server, monkeypatch, capsys
):
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


@pytest.mark.asyncio
async def test_aiohttp_query_with_extensions(event_loop, aiohttp_server):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_with_extensions, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    sample_transport = AIOHTTPTransport(url=url, timeout=10)

    async with Client(transport=sample_transport,) as session:

        query = gql(query1_str)

        execution_result = await session.execute(query, get_execution_result=True)

        assert execution_result.extensions["key1"] == "val1"


@pytest.mark.asyncio
@pytest.mark.parametrize("ssl_close_timeout", [0, 10])
async def test_aiohttp_query_https(event_loop, ssl_aiohttp_server, ssl_close_timeout):
    from aiohttp import web
    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await ssl_aiohttp_server(app)

    url = server.make_url("/")

    assert str(url).startswith("https://")

    sample_transport = AIOHTTPTransport(
        url=url, timeout=10, ssl_close_timeout=ssl_close_timeout
    )

    async with Client(transport=sample_transport,) as session:

        query = gql(query1_str)

        # Execute query asynchronously
        result = await session.execute(query)

        continents = result["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"
