"""
HTTP Multipart Transport for GraphQL Subscriptions

This transport implements support for GraphQL subscriptions over HTTP using
the multipart subscription protocol as implemented by Apollo GraphOS Router
and other compatible servers.

Reference:
https://www.apollographql.com/docs/graphos/routing/operations/subscriptions/multipart-protocol
"""

import asyncio
import json
import logging
from ssl import SSLContext
from typing import Any, AsyncGenerator, Callable, Dict, Optional, Union

import aiohttp
from aiohttp.client_reqrep import Fingerprint
from aiohttp.helpers import BasicAuth
from aiohttp.typedefs import LooseCookies, LooseHeaders
from graphql import ExecutionResult
from multidict import CIMultiDictProxy

from gql.graphql_request import GraphQLRequest
from gql.transport.async_transport import AsyncTransport
from gql.transport.common.aiohttp_closed_event import create_aiohttp_closed_event
from gql.transport.exceptions import (
    TransportAlreadyConnected,
    TransportClosed,
    TransportConnectionFailed,
    TransportProtocolError,
    TransportServerError,
)

log = logging.getLogger(__name__)


class HTTPMultipartTransport(AsyncTransport):
    """
    Async Transport for GraphQL subscriptions using the multipart subscription protocol.

    This transport sends GraphQL subscription queries via HTTP POST and receives
    streaming multipart/mixed responses, where each part contains a JSON payload
    with GraphQL execution results. This protocol is implemented by Apollo GraphOS
    Router and other compatible servers.
    """

    def __init__(
        self,
        url: str,
        headers: Optional[LooseHeaders] = None,
        cookies: Optional[LooseCookies] = None,
        auth: Optional[BasicAuth] = None,
        ssl: Union[SSLContext, bool, Fingerprint] = True,
        timeout: Optional[int] = None,
        ssl_close_timeout: Optional[Union[int, float]] = 10,
        json_serialize: Callable = json.dumps,
        json_deserialize: Callable = json.loads,
        client_session_args: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize the HTTP Multipart transport.

        :param url: The GraphQL server URL (http or https)
        :param headers: Dict of HTTP Headers
        :param cookies: Dict of HTTP cookies
        :param auth: BasicAuth object for HTTP authentication
        :param ssl: SSL context or validation mode
        :param timeout: Request timeout in seconds
        :param ssl_close_timeout: Timeout for SSL connection close
        :param json_serialize: JSON serializer function
        :param json_deserialize: JSON deserializer function
        :param client_session_args: Extra args for aiohttp.ClientSession
        """
        self.url = url
        self.headers = headers or {}
        self.cookies = cookies
        self.auth = auth
        self.ssl = ssl
        self.timeout = timeout
        self.ssl_close_timeout = ssl_close_timeout
        self.json_serialize = json_serialize
        self.json_deserialize = json_deserialize
        self.client_session_args = client_session_args or {}

        self.session: Optional[aiohttp.ClientSession] = None
        self.response_headers: Optional[CIMultiDictProxy[str]] = None

    async def connect(self) -> None:
        """Create an aiohttp ClientSession."""
        if self.session is not None:
            raise TransportAlreadyConnected("Transport is already connected")

        client_session_args: Dict[str, Any] = {
            "cookies": self.cookies,
            "headers": self.headers,
            "auth": self.auth,
            "json_serialize": self.json_serialize,
        }

        if self.timeout is not None:
            client_session_args["timeout"] = aiohttp.ClientTimeout(total=self.timeout)

        client_session_args.update(self.client_session_args)

        log.debug("Connecting HTTP Multipart transport")
        self.session = aiohttp.ClientSession(**client_session_args)

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self.session is not None:
            log.debug("Closing HTTP Multipart transport")

            if (
                self.client_session_args
                and self.client_session_args.get("connector_owner") is False
            ):
                log.debug("connector_owner is False -> not closing connector")
            else:
                closed_event = create_aiohttp_closed_event(self.session)
                await self.session.close()
                try:
                    await asyncio.wait_for(closed_event.wait(), self.ssl_close_timeout)
                except asyncio.TimeoutError:
                    pass

        self.session = None

    async def subscribe(
        self,
        request: GraphQLRequest,
    ) -> AsyncGenerator[ExecutionResult, None]:
        """
        Execute a GraphQL subscription and yield results from multipart response.

        :param request: GraphQL request to execute
        :yields: ExecutionResult objects as they arrive in the multipart stream
        """
        if self.session is None:
            raise TransportClosed("Transport is not connected")

        # Prepare the request payload
        payload = request.payload

        # Log the request
        if log.isEnabledFor(logging.DEBUG):
            log.debug(">>> %s", self.json_serialize(payload))

        # Set headers to accept multipart responses
        # The multipart subscription protocol requires subscriptionSpec parameter
        headers = {
            "Content-Type": "application/json",
            "Accept": 'multipart/mixed;subscriptionSpec="1.0", application/json',
        }

        try:
            # Make the POST request
            async with self.session.post(
                self.url,
                json=payload,
                headers=headers,
                ssl=self.ssl,
            ) as response:
                # Save response headers
                self.response_headers = response.headers

                # Check for errors
                if response.status >= 400:
                    error_text = await response.text()
                    raise TransportServerError(
                        f"Server returned {response.status}: {error_text}",
                        response.status,
                    )

                content_type = response.headers.get("Content-Type", "")

                # Check if response is multipart
                if "multipart/mixed" not in content_type:
                    raise TransportProtocolError(
                        f"Expected multipart/mixed response, got {content_type}. "
                        "Server may not support the multipart subscription protocol."
                    )

                # Parse multipart response
                async for result in self._parse_multipart_response(
                    response, content_type
                ):
                    yield result

        except (TransportServerError, TransportProtocolError):
            raise
        except Exception as e:
            raise TransportConnectionFailed(str(e)) from e

    async def _parse_multipart_response(
        self,
        response: aiohttp.ClientResponse,
        content_type: str,
    ) -> AsyncGenerator[ExecutionResult, None]:
        """
        Parse a multipart/mixed response and yield execution results.

        :param response: The aiohttp response object
        :param content_type: The Content-Type header value
        :yields: ExecutionResult objects
        """
        # Extract boundary from Content-Type header
        # Format: multipart/mixed; boundary="---"
        boundary = None
        for part in content_type.split(";"):
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part.split("=", 1)[1].strip('"')
                break

        if not boundary:
            raise TransportProtocolError("No boundary found in multipart response")

        log.debug("Parsing multipart response with boundary: %s", boundary)

        # Read and parse the multipart stream
        buffer = b""
        boundary_bytes = f"--{boundary}".encode()
        end_boundary_bytes = f"--{boundary}--".encode()

        async for chunk in response.content.iter_any():
            buffer += chunk

            # Process complete parts from the buffer
            while True:
                # Look for the next boundary
                boundary_pos = buffer.find(boundary_bytes)
                if boundary_pos == -1:
                    break  # No complete part yet

                # Check if this is the end boundary
                end_pos = boundary_pos + len(end_boundary_bytes)
                if buffer[boundary_pos:end_pos] == end_boundary_bytes:
                    log.debug("Reached end boundary")
                    return

                # Find the start of the next part (after this boundary)
                # Look for either another regular boundary or the end boundary
                next_boundary_pos = buffer.find(
                    boundary_bytes, boundary_pos + len(boundary_bytes)
                )

                if next_boundary_pos == -1:
                    # No next boundary yet, wait for more data
                    break

                # Extract the part between boundaries
                start_pos = boundary_pos + len(boundary_bytes)
                part_data = buffer[start_pos:next_boundary_pos]

                # Parse the part
                try:
                    result = self._parse_multipart_part(part_data)
                    if result:
                        yield result
                except TransportServerError:
                    # Re-raise transport-level errors
                    raise
                except Exception as e:
                    log.warning("Error parsing multipart part: %s", e)

                # Remove processed data from buffer
                buffer = buffer[next_boundary_pos:]

    def _parse_multipart_part(self, part_data: bytes) -> Optional[ExecutionResult]:
        """
        Parse a single part from a multipart response.

        :param part_data: Raw bytes of the part (including headers)
        :return: ExecutionResult or None if part is empty/heartbeat
        """
        # Split headers and body by double CRLF or double LF
        part_str = part_data.decode("utf-8")

        # Try different separators
        if "\r\n\r\n" in part_str:
            parts = part_str.split("\r\n\r\n", 1)
        elif "\n\n" in part_str:
            parts = part_str.split("\n\n", 1)
        else:
            # No headers separator found, treat entire content as body
            parts = ["", part_str]

        if len(parts) < 2:
            return None

        headers_str, body = parts
        body = body.strip()

        if not body:
            return None

        # Log the received data
        if log.isEnabledFor(logging.DEBUG):
            log.debug("<<< %s", body)

        try:
            # Parse JSON body
            data = self.json_deserialize(body)

            # Handle heartbeats - empty JSON objects
            if not data or (len(data) == 0):
                log.debug("Received heartbeat, ignoring")
                return None

            # The multipart subscription protocol wraps data in a "payload" property
            if "payload" in data:
                payload = data["payload"]

                # Check for transport-level errors (payload is null)
                if payload is None:
                    errors = data.get("errors", [])
                    if errors:
                        # Transport-level error, raise exception
                        error_msg = errors[0].get("message", "Unknown transport error")
                        log.error(f"Transport error: {error_msg}")
                        raise TransportServerError(error_msg)
                    return None

                # Extract GraphQL data from payload
                return ExecutionResult(
                    data=payload.get("data"),
                    errors=payload.get("errors"),
                    extensions=payload.get("extensions"),
                )
            else:
                # Fallback: direct format without payload wrapper
                return ExecutionResult(
                    data=data.get("data"),
                    errors=data.get("errors"),
                    extensions=data.get("extensions"),
                )
        except json.JSONDecodeError as e:
            log.warning(f"Failed to parse JSON: {e}, body: {body[:100]}")
            return None

    async def execute(
        self,
        request: GraphQLRequest,
    ) -> ExecutionResult:
        """
        Execute a GraphQL query/mutation and return the first result.

        :param request: GraphQL request to execute
        :return: ExecutionResult
        """
        async for result in self.subscribe(request):
            return result

        raise TransportProtocolError("No result received from server")
