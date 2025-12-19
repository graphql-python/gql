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

        payload = request.payload
        if log.isEnabledFor(logging.DEBUG):
            log.debug(">>> %s", self.json_serialize(payload))

        headers = {
            "Content-Type": "application/json",
            "Accept": (
                "multipart/mixed;boundary=graphql;"
                "subscriptionSpec=1.0,application/json"
            ),
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

                initial_content_type = response.headers.get("Content-Type", "")
                if (
                    ("multipart/mixed" not in initial_content_type)
                    or ("boundary=graphql" not in initial_content_type)
                    or ("subscriptionSpec=1.0" not in initial_content_type)
                    or ("application/json" not in initial_content_type)
                ):
                    raise TransportProtocolError(
                        f"Unexpected content-type: {initial_content_type}. "
                        "Server may not support the multipart subscription protocol."
                    )

                # Parse multipart response
                async for result in self._parse_multipart_response(response):
                    yield result

        except (TransportServerError, TransportProtocolError):
            # Let these exceptions propagate without wrapping
            raise
        except Exception as e:
            raise TransportConnectionFailed(str(e)) from e

    async def _parse_multipart_response(
        self,
        response: aiohttp.ClientResponse,
    ) -> AsyncGenerator[ExecutionResult, None]:
        """
        Parse a multipart response stream and yield execution results.

        Uses aiohttp's built-in MultipartReader to handle the multipart protocol.

        :param response: The aiohttp response object
        :yields: ExecutionResult objects
        """
        # Use aiohttp's built-in multipart reader
        reader = aiohttp.MultipartReader.from_response(response)

        # Iterate through each part in the multipart response
        while True:
            try:
                part = await reader.next()
            except Exception:
                # reader.next() throws on empty parts at the end of the stream.
                # (some servers may send this.)
                # see: https://github.com/aio-libs/aiohttp/pull/11857
                # As an ugly workaround for now, we can check if we've reached
                # EOF and assume this was the case.
                if reader.at_eof():
                    break

                # Otherwise, re-raise unexpected errors
                raise  # pragma: no cover

            if part is None:
                # No more parts
                break

            assert not isinstance(
                part, aiohttp.MultipartReader
            ), "Nested multipart parts are not supported in GraphQL subscriptions"

            result = await self._parse_multipart_part(part)
            if result:
                yield result

    async def _parse_multipart_part(
        self, part: aiohttp.BodyPartReader
    ) -> Optional[ExecutionResult]:
        """
        Parse a single part from a multipart response.

        :param part: aiohttp BodyPartReader for the part
        :return: ExecutionResult or None if part is empty/heartbeat
        """
        # Verify the part has the correct content type
        content_type = part.headers.get(aiohttp.hdrs.CONTENT_TYPE, "")
        if not content_type.startswith("application/json"):
            raise TransportProtocolError(
                f"Unexpected part content-type: {content_type}. "
                "Expected 'application/json'."
            )

        try:
            # Read the part content as text
            body = await part.text()
            body = body.strip()

            if log.isEnabledFor(logging.DEBUG):
                log.debug("<<< %s", body or "(empty body, skipping)")

            if not body:
                return None

            # Parse JSON body using custom deserializer
            data = self.json_deserialize(body)

            # Handle heartbeats - empty JSON objects
            if not data:
                log.debug("Received heartbeat, ignoring")
                return None

            # The multipart subscription protocol wraps data in a "payload" property
            if "payload" not in data:
                log.warning("Invalid response: missing 'payload' field")
                return None

            payload = data["payload"]

            # Check for transport-level errors (payload is null)
            if payload is None:
                # If there are errors, this is a transport-level error
                errors = data.get("errors")
                if errors:
                    error_messages = [
                        error.get("message", "Unknown transport error")
                        for error in errors
                    ]

                    for message in error_messages:
                        log.error(f"Transport error: {message}")

                    raise TransportServerError("\n\n".join(error_messages))
                else:
                    # Null payload without errors - just skip this part
                    return None

            # Extract GraphQL data from payload
            return ExecutionResult(
                data=payload.get("data"),
                errors=payload.get("errors"),
                extensions=payload.get("extensions"),
            )
        except json.JSONDecodeError as e:
            log.warning(
                f"Failed to parse JSON: {e}, body: {body[:100] if body else ''}"
            )
            return None

    async def execute(
        self,
        request: GraphQLRequest,
    ) -> ExecutionResult:
        """
        :raises: NotImplementedError - This transport only supports subscriptions
        """
        raise NotImplementedError(
            "The HTTP multipart transport does not support queries or "
            "mutations. Use HTTPTransport for queries and mutations, or use "
            "subscribe() for subscriptions."
        )
