from typing import Mapping

import pytest

from gql import Client, GraphQLRequest, gql
from gql.transport.exceptions import (
    TransportClosed,
    TransportProtocolError,
    TransportQueryError,
    TransportServerError,
)

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

query1_server_answer_list = (
    '[{"data":{"continents":['
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
    '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
    '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
    '{"code":"SA","name":"South America"}]}}]'
)

query1_server_answer_twice_list = (
    "["
    '{"data":{"continents":['
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
    '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
    '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
    '{"code":"SA","name":"South America"}]}},'
    '{"data":{"continents":['
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
    '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
    '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
    '{"code":"SA","name":"South America"}]}}'
    "]"
)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_query(event_loop, aiohttp_server, run_sync_test):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_list,
            content_type="application/json",
            headers={"dummy": "test1234"},
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        transport = RequestsHTTPTransport(url=url)

        with Client(transport=transport) as session:

            query = [GraphQLRequest(document=gql(query1_str))]

            # Execute query synchronously
            results = session.execute_batch(query)

            continents = results[0]["continents"]

            africa = continents[0]

            assert africa["code"] == "AF"

            # Checking response headers are saved in the transport
            assert hasattr(transport, "response_headers")
            assert isinstance(transport.response_headers, Mapping)
            assert transport.response_headers["dummy"] == "test1234"

    await run_sync_test(event_loop, server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_query_auto_batch_enabled(
    event_loop, aiohttp_server, run_sync_test
):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_list,
            content_type="application/json",
            headers={"dummy": "test1234"},
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        transport = RequestsHTTPTransport(url=url)

        with Client(
            transport=transport,
            batch_interval=0.01,
        ) as session:

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

    await run_sync_test(event_loop, server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_query_auto_batch_enabled_two_requests(
    event_loop, aiohttp_server, run_sync_test
):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport
    from threading import Thread

    async def handler(request):
        return web.Response(
            text=query1_server_answer_twice_list,
            content_type="application/json",
            headers={"dummy": "test1234"},
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        transport = RequestsHTTPTransport(url=url)

        threads = []

        with Client(
            transport=transport,
            batch_interval=0.01,
        ) as session:

            def test_thread():
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

            for _ in range(2):
                thread = Thread(target=test_thread)
                thread.start()
                threads.append(thread)

        for thread in threads:
            thread.join()

    await run_sync_test(event_loop, server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_cookies(event_loop, aiohttp_server, run_sync_test):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        assert "COOKIE" in request.headers
        assert "cookie1=val1" == request.headers["COOKIE"]

        return web.Response(
            text=query1_server_answer_list, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        transport = RequestsHTTPTransport(url=url, cookies={"cookie1": "val1"})

        with Client(transport=transport) as session:

            query = [GraphQLRequest(document=gql(query1_str))]

            # Execute query synchronously
            results = session.execute_batch(query)

            continents = results[0]["continents"]

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
        transport = RequestsHTTPTransport(url=url)

        with Client(transport=transport) as session:

            query = [GraphQLRequest(document=gql(query1_str))]

            with pytest.raises(TransportServerError) as exc_info:
                session.execute_batch(query)

            assert "401 Client Error: Unauthorized" in str(exc_info.value)

    await run_sync_test(event_loop, server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_error_code_401_auto_batch_enabled(
    event_loop, aiohttp_server, run_sync_test
):
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
        transport = RequestsHTTPTransport(url=url)

        with Client(
            transport=transport,
            batch_interval=0.01,
        ) as session:

            query = gql(query1_str)

            with pytest.raises(TransportServerError) as exc_info:
                session.execute(query)

            assert "401 Client Error: Unauthorized" in str(exc_info.value)

    await run_sync_test(event_loop, server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_error_code_429(event_loop, aiohttp_server, run_sync_test):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

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

    url = server.make_url("/")

    def test_code():
        transport = RequestsHTTPTransport(url=url)

        with Client(transport=transport) as session:

            query = [GraphQLRequest(document=gql(query1_str))]

            with pytest.raises(TransportServerError) as exc_info:
                session.execute_batch(query)

            assert "429, message='Too Many Requests'" in str(exc_info.value)

        # Checking response headers are saved in the transport
        assert hasattr(transport, "response_headers")
        assert isinstance(transport.response_headers, Mapping)
        assert transport.response_headers["Retry-After"] == "3600"


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
        transport = RequestsHTTPTransport(url=url)

        with Client(transport=transport) as session:

            query = [GraphQLRequest(document=gql(query1_str))]

            with pytest.raises(TransportServerError):
                session.execute_batch(query)

    await run_sync_test(event_loop, server, test_code)


query1_server_error_answer_list = '[{"errors": ["Error 1", "Error 2"]}]'


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_error_code(event_loop, aiohttp_server, run_sync_test):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        return web.Response(
            text=query1_server_error_answer_list, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        transport = RequestsHTTPTransport(url=url)

        with Client(transport=transport) as session:

            query = [GraphQLRequest(document=gql(query1_str))]

            with pytest.raises(TransportQueryError):
                session.execute_batch(query)

    await run_sync_test(event_loop, server, test_code)


invalid_protocol_responses = [
    "{}",
    "qlsjfqsdlkj",
    '{"not_data_or_errors": 35}',
    "[{}]",
    "[qlsjfqsdlkj]",
    '[{"not_data_or_errors": 35}]',
    "[]",
    "[1]",
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
        transport = RequestsHTTPTransport(url=url)

        with Client(transport=transport) as session:

            query = [GraphQLRequest(document=gql(query1_str))]

            with pytest.raises(TransportProtocolError):
                session.execute_batch(query)

    await run_sync_test(event_loop, server, test_code)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_requests_cannot_execute_if_not_connected(
    event_loop, aiohttp_server, run_sync_test
):
    from aiohttp import web
    from gql.transport.requests import RequestsHTTPTransport

    async def handler(request):
        return web.Response(
            text=query1_server_answer_list, content_type="application/json"
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        transport = RequestsHTTPTransport(url=url)

        query = [GraphQLRequest(document=gql(query1_str))]

        with pytest.raises(TransportClosed):
            transport.execute_batch(query)

    await run_sync_test(event_loop, server, test_code)


query1_server_answer_with_extensions_list = (
    '[{"data":{"continents":['
    '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
    '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
    '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
    '{"code":"SA","name":"South America"}]},'
    '"extensions": {"key1": "val1"}'
    "}]"
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
            text=query1_server_answer_with_extensions_list,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")

    def test_code():
        transport = RequestsHTTPTransport(url=url)

        with Client(transport=transport) as session:

            query = [GraphQLRequest(document=gql(query1_str))]

            execution_results = session.execute_batch(query, get_execution_result=True)

            assert execution_results[0].extensions["key1"] == "val1"

    await run_sync_test(event_loop, server, test_code)


ONLINE_URL = "https://countries.trevorblades.com/"

skip_reason = "backend does not support batching anymore..."


@pytest.mark.online
@pytest.mark.requests
@pytest.mark.skip(reason=skip_reason)
def test_requests_sync_batch_auto():

    from threading import Thread
    from gql.transport.requests import RequestsHTTPTransport

    client = Client(
        transport=RequestsHTTPTransport(url=ONLINE_URL),
        batch_interval=0.01,
        batch_max=3,
    )

    query = gql(
        """
        query getContinentName($continent_code: ID!) {
          continent(code: $continent_code) {
            name
          }
        }
        """
    )

    def get_continent_name(session, continent_code):
        variables = {
            "continent_code": continent_code,
        }

        result = session.execute(query, variable_values=variables)

        name = result["continent"]["name"]
        print(f"The continent with the code {continent_code} has the name: '{name}'")

    continent_codes = ["EU", "AF", "NA", "OC", "SA", "AS", "AN"]

    with client as session:

        for continent_code in continent_codes:

            thread = Thread(
                target=get_continent_name,
                args=(
                    session,
                    continent_code,
                ),
            )
            thread.start()
            thread.join()

    # Doing it twice to check that everything is closing and reconnecting correctly
    with client as session:

        for continent_code in continent_codes:

            thread = Thread(
                target=get_continent_name,
                args=(
                    session,
                    continent_code,
                ),
            )
            thread.start()
            thread.join()


@pytest.mark.online
@pytest.mark.requests
@pytest.mark.skip(reason=skip_reason)
def test_requests_sync_batch_auto_execute_future():

    from gql.transport.requests import RequestsHTTPTransport

    client = Client(
        transport=RequestsHTTPTransport(url=ONLINE_URL),
        batch_interval=0.01,
        batch_max=3,
    )

    query = gql(
        """
        query getContinentName($continent_code: ID!) {
          continent(code: $continent_code) {
            name
          }
        }
        """
    )

    with client as session:

        request_eu = GraphQLRequest(query, variable_values={"continent_code": "EU"})
        future_result_eu = session._execute_future(request_eu)

        request_af = GraphQLRequest(query, variable_values={"continent_code": "AF"})
        future_result_af = session._execute_future(request_af)

        result_eu = future_result_eu.result().data
        result_af = future_result_af.result().data

        assert result_eu["continent"]["name"] == "Europe"
        assert result_af["continent"]["name"] == "Africa"


@pytest.mark.online
@pytest.mark.requests
@pytest.mark.skip(reason=skip_reason)
def test_requests_sync_batch_manual():

    from gql.transport.requests import RequestsHTTPTransport

    client = Client(
        transport=RequestsHTTPTransport(url=ONLINE_URL),
    )

    query = gql(
        """
        query getContinentName($continent_code: ID!) {
          continent(code: $continent_code) {
            name
          }
        }
        """
    )

    with client as session:

        request_eu = GraphQLRequest(query, variable_values={"continent_code": "EU"})
        request_af = GraphQLRequest(query, variable_values={"continent_code": "AF"})

        result_eu, result_af = session.execute_batch([request_eu, request_af])

        assert result_eu["continent"]["name"] == "Europe"
        assert result_af["continent"]["name"] == "Africa"
