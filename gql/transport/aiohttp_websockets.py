import logging
import re
import time
import aiohttp
from gql.transport.async_transport import AsyncTransport
from typing import Any, AsyncGenerator, Dict, Optional, Union, Collection
from aiohttp.typedefs import LooseHeaders, Mapping, StrOrURL
from aiohttp.helpers import hdrs, BasicAuth, _SENTINEL
from gql.transport.exceptions import TransportClosed, TransportProtocolError, TransportQueryError
from graphql import DocumentNode, ExecutionResult
from h11 import Data
from websockets import ConnectionClosed
from gql.transport.websockets_base import ListenerQueue

"""HTTP Client for asyncio."""

from typing import (
    Collection,
    Mapping,
    Optional,
    Union,
)


from aiohttp import hdrs
from aiohttp.client_reqrep import (
    Fingerprint,
)
from aiohttp.helpers import (
    _SENTINEL,
    BasicAuth,
    sentinel,
)
from aiohttp.typedefs import LooseHeaders, StrOrURL

from ssl import SSLContext

log = logging.getLogger("gql.transport.aiohttp_websockets")

class AIOHTTPWebsocketsTransport(AsyncTransport):

    def __init__(
        self,
        url: StrOrURL,
        *,
        method: str = hdrs.METH_GET,
        protocols: Collection[str] = (),
        timeout: Union[float, _SENTINEL, None] = sentinel,
        receive_timeout: Optional[float] = None,
        autoclose: bool = True,
        autoping: bool = True,
        heartbeat: Optional[float] = None,
        auth: Optional[BasicAuth] = None,
        origin: Optional[str] = None,
        params: Optional[Mapping[str, str]] = None,
        headers: Optional[LooseHeaders] = None,
        proxy: Optional[StrOrURL] = None,
        proxy_auth: Optional[BasicAuth] = None,
        ssl: Union[SSLContext, bool, Fingerprint] = True,
        ssl_context: Optional[SSLContext] = None,
        verify_ssl: Optional[bool] = True,
        server_hostname: Optional[str] = None,
        proxy_headers: Optional[LooseHeaders] = None,
        compress: int = 0,
        max_msg_size: int = 4 * 1024 * 1024,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.url: str = url
        self.headers: Optional[LooseHeaders] = headers
        self.auth: Optional[BasicAuth] = auth
        self.autoclose: bool = autoclose
        self.autoping: bool = autoping
        self.compress: int = compress
        self.heartbeat: Optional[float] = heartbeat
        self.max_msg_size: int = max_msg_size
        self.method: str = method
        self.origin: Optional[str] = origin
        self.params: Optional[Mapping[str, str]] = params
        self.protocols: Optional[list[str]] = protocols
        self.proxy: Optional[StrOrURL] = proxy
        self.proxy_auth: Optional[BasicAuth] = proxy_auth
        self.proxy_headers: Optional[LooseHeaders] = proxy_headers
        self.receive_timeout: Optional[float] = receive_timeout
        self.ssl: Union[SSLContext, bool] = ssl
        self.ssl_context: Optional[SSLContext] = ssl_context
        self.timeout: Union[float, _SENTINEL, None] = timeout        
        self.verify_ssl: Optional[bool] = verify_ssl


        self.session: Optional[aiohttp.ClientSession] = None
        self.websocket: Optional[aiohttp.ClientWebSocketResponse] = None


    async def _initialize(self):
        """Hook to send the initialization messages after the connection
        and potentially wait for the backend ack.
        """
        pass  # pragma: no cover

    async def _stop_listener(self, query_id: int):
        """Hook to stop to listen to a specific query.
        Will send a stop message in some subclasses.
        """
        pass  # pragma: no cover

    async def _after_connect(self):
        """Hook to add custom code for subclasses after the connection
        has been established.
        """
        pass  # pragma: no cover

    async def _after_initialize(self):
        """Hook to add custom code for subclasses after the initialization
        has been done.
        """
        pass  # pragma: no cover

    async def _close_hook(self):
        """Hook to add custom code for subclasses for the connection close"""
        pass  # pragma: no cover

    async def _connection_terminate(self):
        """Hook to add custom code for subclasses after the initialization
        has been done.
        """
        pass  # pragma: no cover

    async def _send(self, message: str) -> None:
        if self.websocket is None:
            raise TransportClosed("WebSocket connection is closed")

        try:
            await self.websocket.send_str(message)
            log.info(">>> %s", message)
        except ConnectionClosed as e:
            await self._fail(e, clean_close=False)
            raise e
    
    async def _receive(self) -> str:

        if self.websocket is None:
            raise TransportClosed("WebSocket connection is closed")

        data: Data  = await self.websocket.receive()

        if not isinstance(data, str):
            raise TransportProtocolError("Binary data received in the websocket")
        
        answer: str = data
        
        log.info("<<< %s", answer)

        return answer

    async def connect(self) -> None:
        if self.session is None:
            self.session = aiohttp.ClientSession()

        if self.session is not None:
            try:
                self.websocket = await self.session.ws_connect(
                    method=self.method,
                    url=self.url,
                    headers=self.headers,
                    auth=self.auth,
                    autoclose=self.autoclose,
                    autoping=self.autoping,
                    compress=self.compress,
                    heartbeat=self.heartbeat,
                    max_msg_size=self.max_msg_size,
                    origin=self.origin,
                    params=self.params,
                    protocols=self.protocols,
                    proxy=self.proxy,
                    proxy_auth=self.proxy_auth,
                    proxy_headers=self.proxy_headers,
                    receive_timeout=self.receive_timeout,
                    ssl=self.ssl,
                    ssl_context=None,
                    timeout=self.timeout,
                    verify_ssl=self.verify_ssl,
                )
            except Exception as e:
                raise e
            finally:
                ...

    async def close(self) -> None: ...

    async def execute(
        self,
        document: DocumentNode,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute the provided document AST against the configured remote server
        using the current session.

        Send a query but close the async generator as soon as we have the first answer.

        The result is sent as an ExecutionResult object.
        """
        first_result = None

        generator = self.subscribe(
            document, variable_values, operation_name, send_stop=False
        )

        async for result in generator:
            first_result = result

            # Note: we need to run generator.aclose() here or the finally block in
            # the subscribe will not be reached in pypy3 (python version 3.6.1)
            await generator.aclose()

            break

        if first_result is None:
            raise TransportQueryError(
                "Query completed without any answer received from the server"
            )

        return first_result

    async def subscribe(
        self,
        document: DocumentNode,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        send_stop: Optional[bool] = True,
    ) -> AsyncGenerator[ExecutionResult, None]: ...
