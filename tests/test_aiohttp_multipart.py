import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from gql import Client, gql
from gql.graphql_request import GraphQLRequest
from gql.transport.exceptions import (
    TransportClosed,
    TransportConnectionFailed,
    TransportProtocolError,
    TransportServerError,
)

# Marking all tests in this file with the aiohttp marker
pytestmark = pytest.mark.aiohttp

subscription_str = """
    subscription {
      book {
        title
        author
      }
    }
"""

book1 = {"title": "Book 1", "author": "Author 1"}
book2 = {"title": "Book 2", "author": "Author 2"}
book3 = {"title": "Book 3", "author": "Author 3"}


def create_multipart_response(books, *, separator="\r\n", include_heartbeat=False):
    """Helper to create parts for a streamed response body."""
    parts = []

    for idx, book in enumerate(books):
        data = {"data": {"book": book}}
        payload = {"payload": data}

        parts.append((
            f"--graphql{separator}"
            f"Content-Type: application/json{separator}"
            f"{separator}"
            f"{json.dumps(payload)}{separator}"
        ))  # fmt: skip

        # Add heartbeat after first item if requested
        if include_heartbeat and idx == 0:
            parts.append((
                f"--graphql{separator}"
                f"Content-Type: application/json{separator}"
                f"{separator}"
                f"{{}}{separator}"
            ))  # fmt: skip

    # Add end boundary
    parts.append(f"--graphql--{separator}")

    return parts


@pytest.fixture
def multipart_server(aiohttp_server):
    from aiohttp import web

    async def create_server(
        parts,
        *,
        content_type=(
            "multipart/mixed;boundary=graphql;subscriptionSpec=1.0,application/json"
        ),
        request_handler=lambda *args: None,
    ):
        async def handler(request):
            request_handler(request)
            response = web.StreamResponse()
            response.headers["Content-Type"] = content_type
            response.enable_chunked_encoding()
            await response.prepare(request)
            for part in parts:
                if isinstance(part, str):
                    await response.write(part.encode())
                else:
                    await response.write(part)
                await asyncio.sleep(0)  # force the chunk to be written
            await response.write_eof()
            return response

        app = web.Application()
        app.router.add_route("POST", "/", handler)
        server = await aiohttp_server(app)
        return server

    return create_server


@pytest.mark.asyncio
async def test_aiohttp_multipart_subscription(multipart_server):
    from gql.transport.aiohttp import AIOHTTPTransport

    def assert_response_headers(request):
        # Verify the Accept header follows the spec
        accept_header = request.headers["accept"]
        assert "multipart/mixed" in accept_header
        assert "boundary=graphql" in accept_header
        assert "subscriptionSpec=1.0" in accept_header
        assert "application/json" in accept_header

    parts = create_multipart_response([book1, book2])
    server = await multipart_server(parts, request_handler=assert_response_headers)
    url = server.make_url("/")
    transport = AIOHTTPTransport(url=url)

    query = gql(subscription_str)

    async with Client(transport=transport) as session:
        results = []
        async for result in session.subscribe(query):
            results.append(result)

        # Heartbeats should be filtered out
        assert len(results) == 2
        assert results[0]["book"]["title"] == "Book 1"
        assert results[1]["book"]["title"] == "Book 2"


@pytest.mark.asyncio
async def test_aiohttp_multipart_subscription_with_heartbeat(multipart_server):
    from gql.transport.aiohttp import AIOHTTPTransport

    parts = create_multipart_response([book1, book2], include_heartbeat=True)
    server = await multipart_server(parts)
    url = server.make_url("/")
    transport = AIOHTTPTransport(url=url)

    query = gql(subscription_str)

    async with Client(transport=transport) as session:
        results = []
        async for result in session.subscribe(query):
            results.append(result)

        # Heartbeats should be filtered out
        assert len(results) == 2
        assert results[0]["book"]["title"] == "Book 1"
        assert results[1]["book"]["title"] == "Book 2"


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_aiohttp_multipart_unsupported_content_type(aiohttp_server):
    from aiohttp import web

    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        # Return text/html instead of application/json
        return web.Response(text="<p>hello</p>", content_type="text/html")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)
    transport = AIOHTTPTransport(url=server.make_url("/"))

    query = gql(subscription_str)

    async with Client(transport=transport) as session:
        with pytest.raises(TransportProtocolError) as exc_info:
            async for result in session.subscribe(query):
                pass

        assert "Unexpected content-type" in str(exc_info.value)


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_aiohttp_multipart_server_error(aiohttp_server):
    from aiohttp import web

    from gql.transport.aiohttp import AIOHTTPTransport

    async def handler(request):
        return web.Response(text="Internal Server Error", status=500)

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)
    transport = AIOHTTPTransport(url=server.make_url("/"))

    query = gql(subscription_str)

    async with Client(transport=transport) as session:
        with pytest.raises(TransportServerError) as exc_info:
            async for result in session.subscribe(query):
                pass

        assert "Internal Server Error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_aiohttp_multipart_transport_not_connected(multipart_server):
    from gql.transport.aiohttp import AIOHTTPTransport

    parts = create_multipart_response([book1])
    server = await multipart_server(parts)
    transport = AIOHTTPTransport(url=server.make_url("/"))

    query = gql(subscription_str)
    request = GraphQLRequest(query)

    with pytest.raises(TransportClosed):
        async for result in transport.subscribe(request):
            pass


@pytest.mark.asyncio
async def test_aiohttp_multipart_transport_level_error(multipart_server):
    from gql.transport.aiohttp import AIOHTTPTransport

    # Transport error has null payload with errors at top level
    error_response = {
        "payload": None,
        "errors": [{"message": "Transport connection failed"}],
    }
    parts = [
        (
            "--graphql\r\n"
            "Content-Type: application/json\r\n"
            "\r\n"
            f"{json.dumps(error_response)}\r\n"
        ),
        "--graphql--\r\n",
    ]

    server = await multipart_server(parts)
    url = server.make_url("/")
    transport = AIOHTTPTransport(url=url)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)

        with pytest.raises(TransportServerError) as exc_info:
            async for result in session.subscribe(query):
                pass

        assert "Transport connection failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_aiohttp_multipart_graphql_errors(multipart_server):
    from gql.transport.aiohttp import AIOHTTPTransport
    from gql.transport.exceptions import TransportQueryError

    # GraphQL errors come inside the payload
    response = {
        "payload": {
            "data": {"book": {**book1, "author": None}},
            "errors": [
                {"message": "could not fetch author", "path": ["book", "author"]}
            ],
        }
    }
    parts = [
        (
            f"--graphql\r\n"
            f"Content-Type: application/json\r\n"
            f"\r\n"
            f"{json.dumps(response)}\r\n"
        ),
        "--graphql--\r\n",
    ]

    server = await multipart_server(parts)
    url = server.make_url("/")
    transport = AIOHTTPTransport(url=url)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)

        # Client raises TransportQueryError when there are errors in the result
        with pytest.raises(TransportQueryError) as exc_info:
            async for result in session.subscribe(query):
                pass

        # Verify error details
        assert "could not fetch author" in str(exc_info.value).lower()
        assert exc_info.value.data is not None
        assert exc_info.value.data["book"]["author"] is None
        # Verify we can still get data for the non-error fields
        assert exc_info.value.data["book"]["title"] == "Book 1"


@pytest.mark.asyncio
async def test_aiohttp_multipart_newline_separator(multipart_server):
    """Test that LF-only separators are rejected (spec requires CRLF)."""
    from gql.transport.aiohttp import AIOHTTPTransport

    # The GraphQL over HTTP spec requires CRLF line endings in multipart responses
    # https://github.com/graphql/graphql-over-http/blob/main/rfcs/IncrementalDelivery.md
    parts = create_multipart_response([book1], separator="\n")
    server = await multipart_server(parts)
    transport = AIOHTTPTransport(url=server.make_url("/"))

    query = gql(subscription_str)

    async with Client(transport=transport) as session:
        # Non-compliant multipart format (LF instead of CRLF) should fail
        with pytest.raises(TransportConnectionFailed):
            async for result in session.subscribe(query):
                pass


@pytest.mark.asyncio
async def test_aiohttp_multipart_ssl_close_timeout(multipart_server):
    """Test SSL close timeout during transport close."""
    from gql.transport.aiohttp import AIOHTTPTransport

    parts = create_multipart_response([book1], separator="\n")
    server = await multipart_server(parts)
    url = server.make_url("/")

    transport = AIOHTTPTransport(url=url, ssl_close_timeout=0.001)

    await transport.connect()

    # Mock the closed event to timeout
    with patch(
        "gql.transport.common.aiohttp_closed_event.create_aiohttp_closed_event"
    ) as mock_event:
        mock_wait = AsyncMock()
        mock_wait.side_effect = asyncio.TimeoutError()
        mock_event.return_value.wait = mock_wait

        # Should handle timeout gracefully
        await transport.close()


@pytest.mark.asyncio
async def test_aiohttp_multipart_malformed_json(multipart_server):
    """Test handling of malformed JSON in multipart response."""
    from gql.transport.aiohttp import AIOHTTPTransport

    parts = [
        (
            "--graphql\r\n"
            "Content-Type: application/json\r\n"
            "\r\n"
            "{invalid json }\r\n"
        ),
        "--graphql--\r\n",
    ]

    server = await multipart_server(parts)
    url = server.make_url("/")
    transport = AIOHTTPTransport(url=url)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)

        results = []
        async for result in session.subscribe(query):
            results.append(result)

        # Should skip malformed parts
        assert len(results) == 0


@pytest.mark.asyncio
async def test_aiohttp_multipart_payload_null_no_errors(multipart_server):
    """Test handling of null payload without errors."""
    from gql.transport.aiohttp import AIOHTTPTransport

    # Null payload but no errors
    response = {"payload": None}
    parts = [
        (
            "--graphql\r\n"
            "Content-Type: application/json\r\n"
            "\r\n"
            f"{json.dumps(response)}\r\n"
        ),
        "--graphql--\r\n",
    ]

    server = await multipart_server(parts)
    url = server.make_url("/")
    transport = AIOHTTPTransport(url=url)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)
        results = []
        async for result in session.subscribe(query):
            results.append(result)

        # Null payload without errors should return nothing
        assert len(results) == 0


@pytest.mark.asyncio
async def test_aiohttp_multipart_invalid_utf8(multipart_server):
    """Test handling of invalid UTF-8 in multipart response."""
    from gql.transport.aiohttp import AIOHTTPTransport

    parts = [
        (
            "--graphql\r\n"
            "Content-Type: application/json\r\n"
            "\r\n"
            "\xff\xfe\r\n"  # Contains invalid UTF-8
        ),
        "--graphql--\r\n",
    ]

    server = await multipart_server(parts)
    url = server.make_url("/")
    transport = AIOHTTPTransport(url=url)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)
        results = []
        async for result in session.subscribe(query):
            results.append(result)

        # Should skip invalid part
        assert len(results) == 0


@pytest.mark.asyncio
async def test_aiohttp_multipart_chunked_boundary_split(multipart_server):
    """Test parsing when boundary is split across chunks."""
    from gql.transport.aiohttp import AIOHTTPTransport

    parts = [
        "--gra",
        (
            "phql\r\nContent-Type: application/json\r\n\r\n"
            '{"payload": {"data": {"book": {"title": "Bo'
        ),
        'ok 1"}}}}\r\n--graphql--\r\n',
    ]

    server = await multipart_server(parts)
    url = server.make_url("/")
    transport = AIOHTTPTransport(url=url)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)
        results = []
        async for result in session.subscribe(query):
            results.append(result)

        assert len(results) == 1
        assert results[0]["book"]["title"] == "Book 1"


@pytest.mark.asyncio
async def test_aiohttp_multipart_wrong_part_content_type(multipart_server):
    """Test that parts with wrong content-type raise an error."""
    from gql.transport.aiohttp import AIOHTTPTransport

    # Part with text/html instead of application/json
    parts = [
        ("--graphql\r\n" "Content-Type: text/html\r\n" "\r\n" "<p>hello</p>\r\n"),
        "--graphql--\r\n",
    ]

    server = await multipart_server(parts)
    url = server.make_url("/")
    transport = AIOHTTPTransport(url=url)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)

        with pytest.raises(TransportProtocolError) as exc_info:
            async for result in session.subscribe(query):
                pass

        assert "Unexpected part content-type" in str(exc_info.value)
        assert "text/html" in str(exc_info.value)


@pytest.mark.asyncio
async def test_aiohttp_multipart_response_headers(multipart_server):
    """Test that response headers are captured in the transport."""
    from gql.transport.aiohttp import AIOHTTPTransport

    parts = create_multipart_response([book1])
    server = await multipart_server(parts)
    url = server.make_url("/")
    transport = AIOHTTPTransport(url=url)

    query = gql(subscription_str)

    async with Client(transport=transport) as session:
        results = []
        async for result in session.subscribe(query):
            results.append(result)

        # Verify response headers are captured
        assert transport.response_headers is not None
        assert "Content-Type" in transport.response_headers
        assert "multipart/mixed" in transport.response_headers["Content-Type"]


@pytest.mark.asyncio
async def test_aiohttp_multipart_empty_body(multipart_server):
    """Test part with empty body after stripping."""
    from gql.transport.aiohttp import AIOHTTPTransport

    # Part with only whitespace body
    parts = [
        "--graphql\r\nContent-Type: application/json\r\n\r\n   \r\n",
        "--graphql--\r\n",
    ]

    server = await multipart_server(parts)
    url = server.make_url("/")
    transport = AIOHTTPTransport(url=url)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)
        results = []
        async for result in session.subscribe(query):
            results.append(result)
        assert len(results) == 0


@pytest.mark.asyncio
async def test_aiohttp_multipart_missing_payload_field(multipart_server):
    """Test handling of response missing required 'payload' field."""
    from gql.transport.aiohttp import AIOHTTPTransport

    response = {"foo": "bar"}  # No payload field!
    parts = [
        (
            "--graphql\r\n"
            "Content-Type: application/json\r\n"
            "\r\n"
            f"{json.dumps(response)}\r\n"
        ),
        "--graphql--\r\n",
    ]

    server = await multipart_server(parts)
    url = server.make_url("/")
    transport = AIOHTTPTransport(url=url)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)
        results = []
        async for result in session.subscribe(query):
            results.append(result)

        # Should skip invalid response and return no results
        assert len(results) == 0


@pytest.mark.asyncio
async def test_aiohttp_multipart_with_content_length_headers(multipart_server):
    """Test multipart response with Content-Length headers (like real servers send)."""
    from gql.transport.aiohttp import AIOHTTPTransport

    # Simulate real server behavior: each part has Content-Length header
    book1_payload = json.dumps({"payload": {"data": {"book": book1}}})
    book2_payload = json.dumps({"payload": {"data": {"book": book2}}})
    heartbeat_payload = "{}"

    parts = [
        (
            "--graphql\r\n"
            "Content-Type: application/json; charset=utf-8\r\n"
            f"Content-Length: {len(heartbeat_payload)}\r\n"
            "\r\n"
            f"{heartbeat_payload}\r\n"
        ),
        (
            "--graphql\r\n"
            "Content-Type: application/json; charset=utf-8\r\n"
            f"Content-Length: {len(book1_payload)}\r\n"
            "\r\n"
            f"{book1_payload}\r\n"
        ),
        (
            "--graphql\r\n"
            "Content-Type: application/json; charset=utf-8\r\n"
            f"Content-Length: {len(book2_payload)}\r\n"
            "\r\n"
            f"{book2_payload}\r\n"
        ),
        "--graphql\r\n",  # Extra empty part like real servers
        "--graphql--\r\n",  # Final boundary
    ]

    server = await multipart_server(parts)
    url = server.make_url("/")
    transport = AIOHTTPTransport(url=url)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)
        results = []
        async for result in session.subscribe(query):
            results.append(result)

        # Should get 2 books (heartbeat and empty part filtered)
        assert len(results) == 2
        assert results[0]["book"]["title"] == "Book 1"
        assert results[1]["book"]["title"] == "Book 2"


@pytest.mark.asyncio
async def test_aiohttp_multipart_actually_invalid_utf8(multipart_server):
    """Test handling of ACTUAL invalid UTF-8 bytes in multipart response."""
    from gql.transport.aiohttp import AIOHTTPTransport

    # \\x80 is an invalid start byte in UTF-8
    parts = [
        (
            b"--graphql\r\n"
            b"Content-Type: application/json; charset=utf-8\r\n"
            b"\r\n"
            b"\x80\x81\r\n"
        ),
        b"--graphql--\r\n",
    ]

    server = await multipart_server(parts)
    url = server.make_url("/")
    transport = AIOHTTPTransport(url=url)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)
        results = []
        async for result in session.subscribe(query):
            results.append(result)

        # Should skip invalid part and not crash
        assert len(results) == 0
