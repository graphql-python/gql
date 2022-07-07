import json
import logging
from typing import Any, AsyncGenerator, Callable, Dict, Optional, Union

import httpx
from graphql import DocumentNode, ExecutionResult, print_ast

from .async_transport import AsyncTransport
from .exceptions import (
    TransportAlreadyConnected,
    TransportClosed,
    TransportProtocolError,
    TransportServerError,
)

log = logging.getLogger(__name__)


class HTTPXAsyncTransport(AsyncTransport):
    """:ref:`Async Transport <async_transports>` to execute GraphQL queries
    on remote servers with an HTTP connection.

    This transport use the httpx library with its AsyncClient.
    """

    client: Optional[httpx.AsyncClient] = None
    response_headers: Optional[httpx.Headers] = None

    def __init__(
        self,
        url: Union[str, httpx.URL],
        timeout: Optional[int] = None,
        json_serialize: Callable = json.dumps,
    ) -> None:
        """Initialize the transport with the given httpx parameters.

        :param url: The GraphQL server URL. Example: 'https://server.com:PORT/path'.
        :param json_serialize: Json serializer callable.
                By default json.dumps() function
        """
        self.url: Union[str, httpx.URL] = url
        self.timeout: Optional[int] = timeout
        self.json_serialize: Callable = json_serialize

    async def connect(self) -> None:
        """Coroutine which will create an httpx AsyncClient() as self.client.

        Don't call this coroutine directly on the transport, instead use
        :code:`async with` on the client and this coroutine will be executed
        to create the session.

        Should be cleaned with a call to the close coroutine.
        """

        if self.client is None:
            client_args: Dict[str, Any] = {}

            if self.timeout is not None:
                client_args["timeout"] = self.timeout

            log.debug("Connecting transport")

            self.client = httpx.AsyncClient(**client_args)

        else:
            raise TransportAlreadyConnected("Transport is already connected")

    async def close(self) -> None:
        """Coroutine which will close the aiohttp session.

        Don't call this coroutine directly on the transport, instead use
        :code:`async with` on the client and this coroutine will be executed
        when you exit the async context manager.
        """
        if self.client is not None:
            await self.client.aclose()
        self.client = None

    async def execute(
        self,
        document: DocumentNode,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        extra_args: Dict[str, Any] = None,
        upload_files: bool = False,
    ) -> ExecutionResult:
        """Execute the provided document AST against the configured remote server
        using the current session.
        This uses the httpx library to perform a HTTP POST request asynchronously
        to the remote server.

        Don't call this coroutine directly on the transport, instead use
        :code:`execute` on a client or a session.

        :param document: the parsed GraphQL request
        :param variable_values: An optional Dict of variable values
        :param operation_name: An optional Operation name for the request
        :param extra_args: additional arguments to send to the aiohttp post method
        :param upload_files: Set to True if you want to put files in the variable values
        :returns: an ExecutionResult object.
        """

        query_str = print_ast(document)

        payload: Dict[str, Any] = {
            "query": query_str,
        }

        if operation_name:
            payload["operationName"] = operation_name

        if upload_files:
            raise NotImplementedError("File upload not implemented for this transport")

        else:
            if variable_values:
                payload["variables"] = variable_values

            if log.isEnabledFor(logging.INFO):
                log.info(">>> %s", self.json_serialize(payload))

            post_args: Any = {"json": payload}

        # Pass post_args to httpx post method
        if extra_args:
            post_args.update(extra_args)

        if self.client is None:
            raise TransportClosed("Transport is not connected")

        def raise_response_error(resp: httpx.Response, reason: str):
            # We raise a TransportServerError if the status code is 400 or higher
            # We raise a TransportProtocolError in the other cases

            try:
                # Raise a ClientResponseError if response status is 400 or higher
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                code = resp.status_code
                reason = httpx.codes.get_reason_phrase(code)
                raise TransportServerError(f"{code}, message='{reason}'", code) from e

            result_text = resp.text
            raise TransportProtocolError(
                f"Server did not return a GraphQL result: "
                f"{reason}: "
                f"{result_text}"
            )

        resp = await self.client.post(url=self.url, **post_args)

        try:
            result = resp.json()
            if log.isEnabledFor(logging.INFO):
                log.info("<<< %s", resp.text)
        except Exception:
            raise_response_error(resp, "Not a JSON answer")

        if "errors" not in result and "data" not in result:
            raise_response_error(resp, 'No "data" or "errors" keys in answer')

        self.response_headers = resp.headers

        return ExecutionResult(
            errors=result.get("errors"),
            data=result.get("data"),
            extensions=result.get("extensions"),
        )

    def subscribe(
        self,
        document: DocumentNode,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
    ) -> AsyncGenerator[ExecutionResult, None]:
        """Subscribe is not supported on HTTP.

        :meta private:
        """
        raise NotImplementedError("The HTTP transport does not support subscriptions")
