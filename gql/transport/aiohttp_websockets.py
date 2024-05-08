import asyncio
from contextlib import suppress
import json
import logging
import re
import time
from tkinter import W
import aiohttp
from gql.transport.async_transport import AsyncTransport
from typing import Any, AsyncGenerator, Dict, Optional, Union, Collection
from aiohttp.typedefs import LooseHeaders, Mapping, StrOrURL
from aiohttp.helpers import hdrs, BasicAuth, _SENTINEL
from gql.transport.exceptions import (
    TransportClosed,
    TransportProtocolError,
    TransportQueryError,
)
from graphql import DocumentNode, ExecutionResult, print_ast
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

    # This transport supports two subprotocols and will autodetect the
    # subprotocol supported on the server
    APOLLO_SUBPROTOCOL: str = "graphql-ws"
    GRAPHQLWS_SUBPROTOCOL: str = "graphql-transport-ws"

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
        connect_timeout: Optional[Union[int, float]] = 10,
        close_timeout: Optional[Union[int, float]] = 10,
        ack_timeout: Optional[Union[int, float]] = 10,
        keep_alive_timeout: Optional[Union[int, float]] = None,
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

        self.connect_timeout: Optional[Union[int, float]] = connect_timeout
        self.close_timeout: Optional[Union[int, float]] = close_timeout
        self.ack_timeout: Optional[Union[int, float]] = ack_timeout
        self.keep_alive_timeout: Optional[Union[int, float]] = keep_alive_timeout

        self.session: Optional[aiohttp.ClientSession] = None
        self.websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self.next_query_id: int = 1
        self.listeners: Dict[int, ListenerQueue] = {}

        self.receive_data_task: Optional[asyncio.Future] = None
        self.check_keep_alive_task: Optional[asyncio.Future] = None
        self.close_task: Optional[asyncio.Future] = None

        self._wait_closed: asyncio.Event = asyncio.Event()
        self._wait_closed.set()

        self._no_more_listeners: asyncio.Event = asyncio.Event()
        self._no_more_listeners.set()

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

        # Find the backend subprotocol returned in the response headers
        # TODO: find the equivalent of response_headers in aiohttp websocket response
        subprotocol = self.websocket.protocol
        try:
            self.subprotocol = subprotocol
        except KeyError:
            # If the server does not send the subprotocol header, using
            # the apollo subprotocol by default
            self.subprotocol = self.APOLLO_SUBPROTOCOL

        log.debug(f"backend subprotocol returned: {self.subprotocol!r}")

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

    async def _send_query(
        self,
        document: DocumentNode,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
    ) -> int:
        """Send a query to the provided websocket connection.

        We use an incremented id to reference the query.

        Returns the used id for this query.
        """

        query_id = self.next_query_id
        self.next_query_id += 1

        payload: Dict[str, Any] = {"query": print_ast(document)}
        if variable_values:
            payload["variables"] = variable_values
        if operation_name:
            payload["operationName"] = operation_name

        query_type = "start"

        if self.subprotocol == self.GRAPHQLWS_SUBPROTOCOL:
            query_type = "subscribe"

        query_str = json.dumps(
            {"id": str(query_id), "type": query_type, "payload": payload}
        )

        await self._send(query_str)

        return query_id

    async def _send(self, message: str) -> None:
        """Send the provided message to the websocket connection and log the message"""

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

        data: Data = await self.websocket.receive()

        if not isinstance(data, str):
            raise TransportProtocolError("Binary data received in the websocket")

        answer: str = data

        log.info("<<< %s", answer)

        return answer

    def _remove_listener(self, query_id) -> None:
        """After exiting from a subscription, remove the listener and
        signal an event if this was the last listener for the client.
        """
        if query_id in self.listeners:
            del self.listeners[query_id]

        remaining = len(self.listeners)
        log.debug(f"listener {query_id} deleted, {remaining} remaining")

        if remaining == 0:
            self._no_more_listeners.set()

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
            await self._after_connect()

    async def _clean_close(self, e: Exception) -> None:
        """Coroutine which will:

        - send stop messages for each active subscription to the server
        - send the connection terminate message
        """

        # Send 'stop' message for all current queries
        for query_id, listener in self.listeners.items():

            if listener.send_stop:
                await self._stop_listener(query_id)
                listener.send_stop = False

        # Wait that there is no more listeners (we received 'complete' for all queries)
        try:
            await asyncio.wait_for(self._no_more_listeners.wait(), self.close_timeout)
        except asyncio.TimeoutError:  # pragma: no cover
            log.debug("Timer close_timeout fired")

        # Calling the subclass hook
        await self._connection_terminate()

    async def _close_coro(self, e: Exception, clean_close: bool = True) -> None:
        """Coroutine which will:

        - do a clean_close if possible:
            - send stop messages for each active query to the server
            - send the connection terminate message
        - close the websocket connection
        - send the exception to all the remaining listeners
        """

        log.debug("_close_coro: starting")

        try:

            # We should always have an active websocket connection here
            assert self.websocket is not None

            # Properly shut down liveness checker if enabled
            if self.check_keep_alive_task is not None:
                # More info: https://stackoverflow.com/a/43810272/1113207
                self.check_keep_alive_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self.check_keep_alive_task

            # Calling the subclass close hook
            await self._close_hook()

            # Saving exception to raise it later if trying to use the transport
            # after it has already closed.
            self.close_exception = e

            if clean_close:
                log.debug("_close_coro: starting clean_close")
                try:
                    await self._clean_close(e)
                except Exception as exc:  # pragma: no cover
                    log.warning("Ignoring exception in _clean_close: " + repr(exc))

            log.debug("_close_coro: sending exception to listeners")

            # Send an exception to all remaining listeners
            for query_id, listener in self.listeners.items():
                await listener.set_exception(e)

            log.debug("_close_coro: close websocket connection")

            await self.websocket.close()

            log.debug("_close_coro: websocket connection closed")

        except Exception as exc:  # pragma: no cover
            log.warning("Exception catched in _close_coro: " + repr(exc))

        finally:

            log.debug("_close_coro: start cleanup")

            self.websocket = None
            self.close_task = None
            self.check_keep_alive_task = None
            self._wait_closed.set()

        log.debug("_close_coro: exiting")
    async def _fail(self, e: Exception, clean_close: bool = True) -> None:
        log.debug("_fail: starting with exception: " + repr(e))

        if self.close_task is None:

            if self.websocket is None:
                log.debug("_fail started with self.websocket == None -> already closed")
            else:
                self.close_task = asyncio.shield(
                    asyncio.ensure_future(self._close_coro(e, clean_close=clean_close))
                )
        else:
            log.debug(
                "close_task is not None in _fail. Previous exception is: "
                + repr(self.close_exception)
                + " New exception is: "
                + repr(e)
            )

    async def close(self) -> None:
        log.debug("close: starting")

        await self._fail(TransportClosed("Websocket GraphQL transport closed by user"))
        await self.wait_closed()

        log.debug("close: done")

    async def wait_closed(self) -> None:
        log.debug("wait_close: starting")

        await self._wait_closed.wait()

        log.debug("wait_close: done")


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
    ) -> AsyncGenerator[ExecutionResult, None]:
        """Send a query and receive the results using a python async generator.

        The query can be a graphql query, mutation or subscription.

        The results are sent as an ExecutionResult object.
        """

        # Send the query and receive the id
        query_id: int = await self._send_query(
            document, variable_values, operation_name
        )

        # Create a queue to receive the answers for this query_id
        listener = ListenerQueue(query_id, send_stop=(send_stop is True))
        self.listeners[query_id] = listener

        # We will need to wait at close for this query to clean properly
        self._no_more_listeners.clear()

        try:
            # Loop over the received answers
            while True:

                # Wait for the answer from the queue of this query_id
                # This can raise a TransportError or ConnectionClosed exception.
                answer_type, execution_result = await listener.get()

                # If the received answer contains data,
                # Then we will yield the results back as an ExecutionResult object
                if execution_result is not None:
                    yield execution_result

                # If we receive a 'complete' answer from the server,
                # Then we will end this async generator output without errors
                elif answer_type == "complete":
                    log.debug(
                        f"Complete received for query {query_id} --> exit without error"
                    )
                    break

        except (asyncio.CancelledError, GeneratorExit) as e:
            log.debug(f"Exception in subscribe: {e!r}")
            if listener.send_stop:
                await self._stop_listener(query_id)
                listener.send_stop = False

        finally:
            log.debug(f"In subscribe finally for query_id {query_id}")
            self._remove_listener(query_id)


