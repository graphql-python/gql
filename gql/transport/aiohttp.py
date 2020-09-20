from ssl import SSLContext
from typing import Any, AsyncGenerator, Dict, Optional, Union

import aiohttp
from aiohttp.client_exceptions import ClientResponseError
from aiohttp.client_reqrep import Fingerprint
from aiohttp.helpers import BasicAuth
from aiohttp.typedefs import LooseCookies, LooseHeaders
from graphql import DocumentNode, ExecutionResult, print_ast

from .async_transport import AsyncTransport
from .exceptions import (
    TransportAlreadyConnected,
    TransportClosed,
    TransportProtocolError,
    TransportServerError,
)


class AIOHTTPTransport(AsyncTransport):
    """:ref:`Async Transport <async_transports>` to execute GraphQL queries
    on remote servers with an HTTP connection.

    This transport use the aiohttp library with asyncio.
    """

    def __init__(
        self,
        url: str,
        headers: Optional[LooseHeaders] = None,
        cookies: Optional[LooseCookies] = None,
        auth: Optional[BasicAuth] = None,
        ssl: Union[SSLContext, bool, Fingerprint] = False,
        timeout: Optional[int] = None,
        client_session_args: Dict[str, Any] = {},
    ) -> None:
        """Initialize the transport with the given aiohttp parameters.

        :param url: The GraphQL server URL. Example: 'https://server.com:PORT/path'.
        :param headers: Dict of HTTP Headers.
        :param cookies: Dict of HTTP cookies.
        :param auth: BasicAuth object to enable Basic HTTP auth if needed
        :param ssl: ssl_context of the connection. Use ssl=False to disable encryption
        :param client_session_args: Dict of extra args passed to
                `aiohttp.ClientSession`_

        .. _aiohttp.ClientSession:
          https://docs.aiohttp.org/en/stable/client_reference.html#aiohttp.ClientSession
        """
        self.url: str = url
        self.headers: Optional[LooseHeaders] = headers
        self.cookies: Optional[LooseCookies] = cookies
        self.auth: Optional[BasicAuth] = auth
        self.ssl: Union[SSLContext, bool, Fingerprint] = ssl
        self.timeout: Optional[int] = timeout
        self.client_session_args = client_session_args

        self.session: Optional[aiohttp.ClientSession] = None

    async def connect(self) -> None:
        """Coroutine which will create an aiohttp ClientSession() as self.session.

        Don't call this coroutine directly on the transport, instead use
        :code:`async with` on the client and this coroutine will be executed
        to create the session.

        Should be cleaned with a call to the close coroutine.
        """

        if self.session is None:

            client_session_args: Dict[str, Any] = {
                "cookies": self.cookies,
                "headers": self.headers,
                "auth": self.auth,
            }

            if self.timeout is not None:
                client_session_args["timeout"] = aiohttp.ClientTimeout(
                    total=self.timeout
                )

            # Adding custom parameters passed from init
            client_session_args.update(self.client_session_args)

            self.session = aiohttp.ClientSession(**client_session_args)

        else:
            raise TransportAlreadyConnected("Transport is already connected")

    async def close(self) -> None:
        """Coroutine which will close the aiohttp session.

        Don't call this coroutine directly on the transport, instead use
        :code:`async with` on the client and this coroutine will be executed
        when you exit the async context manager.
        """
        if self.session is not None:
            await self.session.close()
        self.session = None

    async def execute(
        self,
        document: DocumentNode,
        variable_values: Optional[Dict[str, str]] = None,
        operation_name: Optional[str] = None,
        extra_args: Dict[str, Any] = {},
    ) -> ExecutionResult:
        """Execute the provided document AST against the configured remote server
        using the current session.
        This uses the aiohttp library to perform a HTTP POST request asynchronously
        to the remote server.

        Don't call this coroutine directly on the transport, instead use
        :code:`execute` on a client or a session.

        :param document: the parsed GraphQL request
        :param variables_values: An optional Dict of variable values
        :param operation_name: An optional Operation name for the request
        :param extra_args: additional arguments to send to the aiohttp post method
        :returns: an ExecutionResult object.
        """

        query_str = print_ast(document)
        payload: Dict[str, Any] = {
            "query": query_str,
        }

        if variable_values:
            payload["variables"] = variable_values
        if operation_name:
            payload["operationName"] = operation_name

        post_args = {
            "json": payload,
        }

        # Pass post_args to aiohttp post method
        post_args.update(extra_args)

        if self.session is None:
            raise TransportClosed("Transport is not connected")

        async with self.session.post(self.url, ssl=self.ssl, **post_args) as resp:
            try:
                result = await resp.json()
            except Exception:
                # We raise a TransportServerError if the status code is 400 or higher
                # We raise a TransportProtocolError in the other cases

                try:
                    # Raise a ClientResponseError if response status is 400 or higher
                    resp.raise_for_status()

                except ClientResponseError as e:
                    raise TransportServerError from e

                raise TransportProtocolError("Server did not return a GraphQL result")

            if "errors" not in result and "data" not in result:
                raise TransportProtocolError("Server did not return a GraphQL result")

            return ExecutionResult(errors=result.get("errors"), data=result.get("data"))

    def subscribe(
        self,
        document: DocumentNode,
        variable_values: Optional[Dict[str, str]] = None,
        operation_name: Optional[str] = None,
    ) -> AsyncGenerator[ExecutionResult, None]:
        """Subscribe is not supported on HTTP.

        :meta private:
        """
        raise NotImplementedError(" The HTTP transport does not support subscriptions")
