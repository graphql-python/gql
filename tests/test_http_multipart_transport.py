import asyncio
import json
from typing import Mapping

import pytest

from gql import Client, gql
from gql.graphql_request import GraphQLRequest
from gql.transport.exceptions import (
    TransportAlreadyConnected,
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


def create_multipart_response(books, include_heartbeat=False):
    """Helper to create parts for a streamed response body."""
    parts = []

    for idx, book in enumerate(books):
        data = {"data": {"book": book}}
        payload = {"payload": data}

        parts.append((
            f"--graphql\r\n"
            f"Content-Type: application/json\r\n"
            f"\r\n"
            f"{json.dumps(payload)}\r\n"
        ))

        # Add heartbeat after first item if requested
        if include_heartbeat and idx == 0:
            parts.append((
                "--graphql\r\n"
                "Content-Type: application/json\r\n"
                "\r\n"
                "{}\r\n"
            ))

    # Add end boundary
    parts.append("--graphql--\r\n")

    return "".join(parts)


@pytest.mark.asyncio
async def test_http_multipart_subscription_with_heartbeat(aiohttp_server):
    """Test subscription with heartbeat messages (empty JSON objects)."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        body = create_multipart_response([book1, book2], include_heartbeat=True)
        return web.Response(
            text=body,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = HTTPMultipartTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)

        results = []
        async for result in session.subscribe(query):
            results.append(result)

        # Heartbeats should be filtered out
        assert len(results) == 2
        assert results[0]["book"]["title"] == "Book 1"
        assert results[1]["book"]["title"] == "Book 2"


@pytest.mark.asyncio
async def test_http_multipart_unsupported_content_type(aiohttp_server):
    """Test error when server returns non-JSON content type."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        # Return text/html instead of application/json
        response = {"data": {"book": book1}}
        return web.Response(
            text=json.dumps(response),
            content_type="text/html",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = HTTPMultipartTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)

        with pytest.raises(TransportProtocolError) as exc_info:
            async for result in session.subscribe(query):
                pass

        assert "application/json" in str(exc_info.value)


@pytest.mark.asyncio
async def test_http_multipart_server_error(aiohttp_server):
    """Test handling of HTTP server errors."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        return web.Response(
            text="Internal Server Error",
            status=500,
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = HTTPMultipartTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)

        with pytest.raises(TransportServerError) as exc_info:
            async for result in session.subscribe(query):
                pass

        assert "500" in str(exc_info.value)


@pytest.mark.asyncio
async def test_http_multipart_transport_level_error(aiohttp_server):
    """Test handling of transport-level errors in multipart response."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        # Transport error has null payload with errors at top level
        error_response = {
            "payload": None,
            "errors": [{"message": "Transport connection failed"}],
        }
        part = (
            f"--graphql\r\n"
            f"Content-Type: application/json\r\n"
            f"\r\n"
            f"{json.dumps(error_response)}\r\n"
            f"--graphql--\r\n"
        )
        return web.Response(
            text=part,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = HTTPMultipartTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)

        with pytest.raises(TransportServerError) as exc_info:
            async for result in session.subscribe(query):
                pass

        assert "Transport connection failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_http_multipart_graphql_errors(aiohttp_server):
    """Test handling of GraphQL-level errors in response."""
    from aiohttp import web

    from gql.transport.exceptions import TransportQueryError
    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        # GraphQL errors come inside the payload
        response = {
            "payload": {
                "data": {"book": book1},
                "errors": [{"message": "Field deprecated", "path": ["book", "author"]}],
            }
        }
        part = (
            f"--graphql\r\n"
            f"Content-Type: application/json\r\n"
            f"\r\n"
            f"{json.dumps(response)}\r\n"
            f"--graphql--\r\n"
        )
        return web.Response(
            text=part,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = HTTPMultipartTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)

        # Client raises TransportQueryError when there are errors in the result
        with pytest.raises(TransportQueryError) as exc_info:
            async for result in session.subscribe(query):
                pass

        # Verify error details
        assert "deprecated" in str(exc_info.value).lower()
        assert exc_info.value.data is not None
        assert exc_info.value.data["book"]["title"] == "Book 1"


@pytest.mark.asyncio
async def test_http_multipart_execute_method(aiohttp_server):
    """Test execute method (returns first result only)."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        body = create_multipart_response([book1, book2])
        return web.Response(
            text=body,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = HTTPMultipartTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)

        # execute returns only the first result
        result = await session.execute(query)

        assert result["book"]["title"] == "Book 1"


@pytest.mark.asyncio
async def test_http_multipart_transport_already_connected():
    """Test error when connecting an already connected transport."""
    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    transport = HTTPMultipartTransport(url="http://example.com/graphql")

    await transport.connect()

    with pytest.raises(TransportAlreadyConnected):
        await transport.connect()

    await transport.close()


@pytest.mark.asyncio
async def test_http_multipart_transport_not_connected():
    """Test error when using transport before connecting."""
    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    transport = HTTPMultipartTransport(url="http://example.com/graphql")

    query = gql(subscription_str)
    request = GraphQLRequest(query)

    with pytest.raises(TransportClosed):
        async for result in transport.subscribe(request):
            pass


@pytest.mark.asyncio
async def test_http_multipart_streaming_response(aiohttp_server):
    """Test handling of chunked/streaming multipart response."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        response = web.StreamResponse()
        response.headers["Content-Type"] = "application/json"
        response.headers["X-Custom-Header"] = "test123"
        await response.prepare(request)

        # Send parts with delays to simulate streaming
        for book in [book1, book2, book3]:
            payload = {"data": {"book": book}}
            wrapped = {"payload": payload}
            part = (
                f"--graphql\r\n"
                f"Content-Type: application/json\r\n"
                f"\r\n"
                f"{json.dumps(wrapped)}\r\n"
            )
            await response.write(part.encode())
            await asyncio.sleep(0.01)  # Small delay to simulate streaming

        await response.write(b"--graphql--\r\n")
        await response.write_eof()
        return response

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = HTTPMultipartTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)

        results = []
        async for result in session.subscribe(query):
            results.append(result)

        assert len(results) == 3
        assert results[0]["book"]["title"] == "Book 1"
        assert results[1]["book"]["title"] == "Book 2"
        assert results[2]["book"]["title"] == "Book 3"

        # Check response headers are saved
        assert hasattr(transport, "response_headers")
        assert isinstance(transport.response_headers, Mapping)
        assert transport.response_headers["X-Custom-Header"] == "test123"


@pytest.mark.asyncio
async def test_http_multipart_accept_header(aiohttp_server):
    """Test that proper Accept header is sent with subscription spec."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        # Verify the Accept header follows the spec
        accept_header = request.headers.get("Accept", "")
        assert "multipart/mixed" in accept_header
        assert "boundary=graphql" in accept_header
        assert "subscriptionSpec=1.0" in accept_header
        assert "application/json" in accept_header

        body = create_multipart_response([book1])
        return web.Response(
            text=body,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = HTTPMultipartTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)

        results = []
        async for result in session.subscribe(query):
            results.append(result)

        assert len(results) == 1


@pytest.mark.asyncio
async def test_http_multipart_execute_empty_response(aiohttp_server):
    """Test execute method with empty response (no results)."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        # Return empty multipart response (no data parts)
        body = "--graphql--\r\n"
        return web.Response(
            text=body,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = HTTPMultipartTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)

        with pytest.raises(TransportProtocolError) as exc_info:
            await session.execute(query)

        assert "No result received" in str(exc_info.value)


@pytest.mark.asyncio
async def test_http_multipart_response_without_payload_wrapper(aiohttp_server):
    """Test parsing response without payload wrapper (direct format)."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        # Send data in direct format (no payload wrapper)
        response = {"data": {"book": book1}}
        part = (
            f"--graphql\r\n"
            f"Content-Type: application/json\r\n"
            f"\r\n"
            f"{json.dumps(response)}\r\n"
            f"--graphql--\r\n"
        )
        return web.Response(
            text=part,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = HTTPMultipartTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)

        results = []
        async for result in session.subscribe(query):
            results.append(result)

        assert len(results) == 1
        assert results[0]["book"]["title"] == "Book 1"


@pytest.mark.asyncio
async def test_http_multipart_newline_separator(aiohttp_server):
    """Test parsing multipart response with LF separator instead of CRLF."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        # Use LF instead of CRLF
        payload = {"data": {"book": book1}}
        wrapped = {"payload": payload}
        part = (
            f"--graphql\n"
            f"Content-Type: application/json\n"
            f"\n"
            f"{json.dumps(wrapped)}\n"
            f"--graphql--\n"
        )
        return web.Response(
            text=part,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = HTTPMultipartTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)

        results = []
        async for result in session.subscribe(query):
            results.append(result)

        assert len(results) == 1
        assert results[0]["book"]["title"] == "Book 1"


@pytest.mark.asyncio
async def test_http_multipart_connection_error():
    """Test handling of connection errors (non-transport exceptions)."""
    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    # Use an invalid URL that will fail to connect
    transport = HTTPMultipartTransport(
        url="http://invalid.local:99999/graphql", timeout=1
    )

    async with Client(transport=transport) as session:
        query = gql(subscription_str)

        with pytest.raises(TransportConnectionFailed):
            async for result in session.subscribe(query):
                pass


@pytest.mark.asyncio
async def test_http_multipart_connector_owner_false(aiohttp_server):
    """Test closing transport with connector_owner=False."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        body = create_multipart_response([book1])
        return web.Response(
            text=body,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    # Create transport with connector_owner=False
    transport = HTTPMultipartTransport(
        url=url, timeout=10, client_session_args={"connector_owner": False}
    )

    async with Client(transport=transport) as session:
        query = gql(subscription_str)
        results = []
        async for result in session.subscribe(query):
            results.append(result)

        assert len(results) == 1


@pytest.mark.asyncio
async def test_http_multipart_ssl_close_timeout(aiohttp_server):
    """Test SSL close timeout during transport close."""
    from unittest.mock import AsyncMock, patch

    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        body = create_multipart_response([book1])
        return web.Response(
            text=body,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = HTTPMultipartTransport(url=url, timeout=10, ssl_close_timeout=0.001)

    await transport.connect()

    # Mock the closed event to timeout
    with patch(
        "gql.transport.http_multipart_transport.create_aiohttp_closed_event"
    ) as mock_event:
        mock_wait = AsyncMock()
        mock_wait.side_effect = asyncio.TimeoutError()
        mock_event.return_value.wait = mock_wait

        # Should handle timeout gracefully
        await transport.close()


@pytest.mark.asyncio
async def test_http_multipart_malformed_json(aiohttp_server):
    """Test handling of malformed JSON in multipart response."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        # Send invalid JSON
        part = (
            "--graphql\r\n"
            "Content-Type: application/json\r\n"
            "\r\n"
            "{invalid json}\r\n"
            "--graphql--\r\n"
        )
        return web.Response(
            text=part,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = HTTPMultipartTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)

        results = []
        async for result in session.subscribe(query):
            results.append(result)

        # Should skip malformed parts
        assert len(results) == 0


@pytest.mark.asyncio
async def test_http_multipart_payload_null_no_errors(aiohttp_server):
    """Test handling of null payload without errors."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        # Null payload but no errors
        response = {"payload": None}
        part = (
            f"--graphql\r\n"
            f"Content-Type: application/json\r\n"
            f"\r\n"
            f"{json.dumps(response)}\r\n"
            f"--graphql--\r\n"
        )
        return web.Response(
            text=part,
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = HTTPMultipartTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)
        results = []
        async for result in session.subscribe(query):
            results.append(result)

        # Null payload without errors should return nothing
        assert len(results) == 0


@pytest.mark.asyncio
async def test_http_multipart_invalid_utf8(aiohttp_server):
    """Test handling of invalid UTF-8 in multipart response."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        part = b"--graphql\r\nContent-Type: application/json\r\n\r\n"
        part += b"\xff\xfe"  # Invalid UTF-8!
        part += b"\r\n--graphql--\r\n"
        return web.Response(body=part, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = HTTPMultipartTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)
        results = []
        async for result in session.subscribe(query):
            results.append(result)

        # Should log warning and skip invalid part
        assert len(results) == 0


@pytest.mark.asyncio
async def test_http_multipart_chunked_boundary_split(aiohttp_server):
    """Test parsing when boundary is split across chunks."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        response = web.StreamResponse()
        response.headers["Content-Type"] = "application/json"
        await response.prepare(request)

        # Send first chunk without any complete boundary (just partial data)
        chunk1 = b"--gra"
        chunk2 = (
            b"phql\r\nContent-Type: application/json\r\n\r\n"
            b'{"payload": {"data": {"book": {"title": "Book 1"}}}}\r\n--graphql--\r\n'
        )

        await response.write(chunk1)
        await asyncio.sleep(0.01)
        await response.write(chunk2)
        await response.write_eof()
        return response

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = HTTPMultipartTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)
        results = []
        async for result in session.subscribe(query):
            results.append(result)

        assert len(results) == 1
        assert results[0]["book"]["title"] == "Book 1"


@pytest.mark.asyncio
async def test_http_multipart_part_without_separator(aiohttp_server):
    """Test part with no header/body separator."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        # Part with no separator - tests line 288 (else branch)
        part = "--graphql\r\nsome content without separator--graphql--\r\n"
        return web.Response(text=part, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = HTTPMultipartTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)
        results = []
        async for result in session.subscribe(query):
            results.append(result)
        assert len(results) == 0


@pytest.mark.asyncio
async def test_http_multipart_empty_body(aiohttp_server):
    """Test part with empty body after stripping."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        # Part with only whitespace body - tests line 294
        part = (
            "--graphql\r\nContent-Type: application/json\r\n\r\n   \r\n--graphql--\r\n"
        )
        return web.Response(text=part, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = server.make_url("/")
    transport = HTTPMultipartTransport(url=url, timeout=10)

    async with Client(transport=transport) as session:
        query = gql(subscription_str)
        results = []
        async for result in session.subscribe(query):
            results.append(result)
        assert len(results) == 0
