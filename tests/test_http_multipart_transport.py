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


def create_multipart_response(items, boundary="graphql", include_heartbeat=False):
    """Helper to create a multipart/mixed response body."""
    parts = []

    for item in items:
        payload = {"data": {"book": item}}
        wrapped = {"payload": payload}
        part = (
            f"--{boundary}\r\n"
            f"Content-Type: application/json\r\n"
            f"\r\n"
            f"{json.dumps(wrapped)}\r\n"
        )
        parts.append(part)

        # Add heartbeat after first item if requested
        if include_heartbeat and item == items[0]:
            heartbeat_part = (
                f"--{boundary}\r\n"
                f"Content-Type: application/json\r\n"
                f"\r\n"
                f"{{}}\r\n"
            )
            parts.append(heartbeat_part)

    # Add end boundary
    parts.append(f"--{boundary}--\r\n")

    return "".join(parts)


@pytest.mark.asyncio
async def test_http_multipart_subscription(aiohttp_server):
    """Test basic subscription with multipart response."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        body = create_multipart_response([book1, book2, book3])
        return web.Response(
            text=body,
            content_type='multipart/mixed; boundary="graphql"',
            headers={"X-Custom-Header": "test123"},
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

        assert len(results) == 3
        assert results[0]["book"]["title"] == "Book 1"
        assert results[1]["book"]["title"] == "Book 2"
        assert results[2]["book"]["title"] == "Book 3"

        # Check response headers are saved
        assert hasattr(transport, "response_headers")
        assert isinstance(transport.response_headers, Mapping)
        assert transport.response_headers["X-Custom-Header"] == "test123"


@pytest.mark.asyncio
async def test_http_multipart_subscription_with_heartbeat(aiohttp_server):
    """Test subscription with heartbeat messages (empty JSON objects)."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        body = create_multipart_response([book1, book2], include_heartbeat=True)
        return web.Response(
            text=body,
            content_type='multipart/mixed; boundary="graphql"',
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
    """Test error when server doesn't support multipart protocol."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        # Return single JSON response instead of multipart
        response = {"data": {"book": book1}}
        return web.Response(
            text=json.dumps(response),
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
            async for result in session.subscribe(query):
                pass

        assert "multipart" in str(exc_info.value).lower()


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
            content_type='multipart/mixed; boundary="graphql"',
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
            content_type='multipart/mixed; boundary="graphql"',
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
async def test_http_multipart_missing_boundary(aiohttp_server):
    """Test error handling when boundary is missing from Content-Type."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        return web.Response(
            text="--graphql\r\nContent-Type: application/json\r\n\r\n{}\r\n--graphql--",
            content_type="multipart/mixed",  # No boundary specified
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

        assert "boundary" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_http_multipart_execute_method(aiohttp_server):
    """Test execute method (returns first result only)."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        body = create_multipart_response([book1, book2])
        return web.Response(
            text=body,
            content_type='multipart/mixed; boundary="graphql"',
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
async def test_http_multipart_custom_boundary(aiohttp_server):
    """Test parsing multipart response with custom boundary."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        boundary = "custom-boundary-xyz"
        body = create_multipart_response([book1, book2], boundary=boundary)
        return web.Response(
            text=body,
            content_type=f'multipart/mixed; boundary="{boundary}"',
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

        assert len(results) == 2
        assert results[0]["book"]["title"] == "Book 1"
        assert results[1]["book"]["title"] == "Book 2"


@pytest.mark.asyncio
async def test_http_multipart_streaming_response(aiohttp_server):
    """Test handling of chunked/streaming multipart response."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        response = web.StreamResponse()
        response.headers["Content-Type"] = 'multipart/mixed; boundary="graphql"'
        await response.prepare(request)

        # Send parts with delays to simulate streaming
        for book in [book1, book2]:
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

        assert len(results) == 2
        assert results[0]["book"]["title"] == "Book 1"
        assert results[1]["book"]["title"] == "Book 2"


@pytest.mark.asyncio
async def test_http_multipart_accept_header(aiohttp_server):
    """Test that proper Accept header is sent with subscription spec."""
    from aiohttp import web

    from gql.transport.http_multipart_transport import HTTPMultipartTransport

    async def handler(request):
        # Verify the Accept header
        accept_header = request.headers.get("Accept", "")
        assert "multipart/mixed" in accept_header
        assert 'subscriptionSpec="1.0"' in accept_header
        assert "application/json" in accept_header

        body = create_multipart_response([book1])
        return web.Response(
            text=body,
            content_type='multipart/mixed; boundary="graphql"',
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
            content_type='multipart/mixed; boundary="graphql"',
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
            content_type='multipart/mixed; boundary="graphql"',
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
            content_type='multipart/mixed; boundary="graphql"',
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
