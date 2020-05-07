import aiohttp

from aiohttp.typedefs import LooseCookies, LooseHeaders
from aiohttp.helpers import BasicAuth
from aiohttp.client_reqrep import Fingerprint

from ssl import SSLContext

from typing import Dict, Optional, Union, AsyncGenerator, Any

from graphql.execution import ExecutionResult
from graphql.language.ast import Document
from graphql.language.printer import print_ast

from .async_transport import AsyncTransport
from .exceptions import (
    TransportProtocolError,
    TransportClosed,
    TransportAlreadyConnected,
)


class AIOHTTPTransport(AsyncTransport):
    """Transport to execute GraphQL queries on remote servers with an http connection.

    This transport use the aiohttp library with asyncio

    See README.md for Usage
    """

    def __init__(
        self,
        url: str,
        headers: Optional[LooseHeaders] = None,
        cookies: Optional[LooseCookies] = None,
        auth: Optional[BasicAuth] = None,
        ssl: Union[SSLContext, bool, Fingerprint] = False,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> None:
        """Initialize the transport with the given aiohttp parameters.

        :param url: The GraphQL server URL. Example: 'https://server.com:PORT/path'.
        :param headers: Dict of HTTP Headers.
        :param cookies: Dict of HTTP cookies.
        :param auth: BasicAuth object to enable Basic HTTP auth if needed
        :param ssl: ssl_context of the connection. Use ssl=False to disable encryption
        :param kwargs: Other parameters forwarded to aiohttp.ClientSession
        """
        self.url: str = url
        self.headers: Optional[LooseHeaders] = headers
        self.cookies: Optional[LooseCookies] = cookies
        self.auth: Optional[BasicAuth] = auth
        self.ssl: Union[SSLContext, bool, Fingerprint] = ssl
        self.timeout: Optional[int] = timeout
        self.kwargs = kwargs

        self.session: Optional[aiohttp.ClientSession] = None

    async def connect(self) -> None:
        """Coroutine which will:

        - create an aiohttp ClientSession() as self.session

        Should be cleaned with a call to the close coroutine
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
            client_session_args.update(self.kwargs)

            self.session = aiohttp.ClientSession(**client_session_args)

        else:
            raise TransportAlreadyConnected("Transport is already connected")

    async def close(self) -> None:
        if self.session is not None:
            await self.session.close()
        self.session = None

    async def execute(
        self,
        document: Document,
        variable_values: Optional[Dict[str, str]] = None,
        operation_name: Optional[str] = None,
        **kwargs,
    ) -> ExecutionResult:
        """Execute the provided document AST against the configured remote server.
        This uses the aiohttp library to perform a HTTP POST request asynchronously to the remote server.

        The result is sent as an ExecutionResult object
        """

        query_str = print_ast(document)
        payload = {
            "query": query_str,
            "variables": variable_values or {},
            "operationName": operation_name or "",
        }

        post_args = {
            "json": payload,
        }

        # Pass kwargs to aiohttp post method
        post_args.update(kwargs)

        if self.session is None:
            raise TransportClosed("Transport is not connected")

        async with self.session.post(self.url, ssl=self.ssl, **post_args) as resp:
            try:
                result = await resp.json()
                if not isinstance(result, dict):
                    raise ValueError
            except ValueError:
                result = {}

            if "errors" not in result and "data" not in result:
                resp.raise_for_status()
                raise TransportProtocolError("Server did not return a GraphQL result")

            return ExecutionResult(errors=result.get("errors"), data=result.get("data"))

    def subscribe(
        self,
        document: Document,
        variable_values: Optional[Dict[str, str]] = None,
        operation_name: Optional[str] = None,
    ) -> AsyncGenerator[ExecutionResult, None]:
        raise NotImplementedError(" The HTTP transport does not support subscriptions")
