import asyncio
import logging
import warnings
from abc import abstractmethod
from contextlib import suppress
from typing import Any, AsyncGenerator, Dict, Optional, Tuple, Union

from graphql import ExecutionResult

from ...graphql_request import GraphQLRequest
from ..async_transport import AsyncTransport
from ..exceptions import (
    TransportAlreadyConnected,
    TransportClosed,
    TransportConnectionFailed,
    TransportProtocolError,
    TransportQueryError,
    TransportServerError,
)
from .adapters import AdapterConnection
from .listener_queue import ListenerQueue

log = logging.getLogger("gql.transport.common.base")


class SubscriptionTransportBase(AsyncTransport):
    """abstract :ref:`Async Transport <async_transports>` used to implement
    different subscription protocols (mainly websockets).
    """

    def __init__(
        self,
        *,
        adapter: AdapterConnection,
        connect_timeout: Optional[Union[int, float]] = 10,
        close_timeout: Optional[Union[int, float]] = 10,
        keep_alive_timeout: Optional[Union[int, float]] = None,
    ) -> None:
        """Initialize the transport with the given parameters.

        :param adapter: The connection dependency adapter
        :param connect_timeout: Timeout in seconds for the establishment
            of the connection. If None is provided this will wait forever.
        :param close_timeout: Timeout in seconds for the close. If None is provided
            this will wait forever.
        :param keep_alive_timeout: Optional Timeout in seconds to receive
            a sign of liveness from the server.
        """

        self.connect_timeout: Optional[Union[int, float]] = connect_timeout
        self.close_timeout: Optional[Union[int, float]] = close_timeout
        self.keep_alive_timeout: Optional[Union[int, float]] = keep_alive_timeout
        self.adapter: AdapterConnection = adapter

        self.next_query_id: int = 1
        self.listeners: Dict[int, ListenerQueue] = {}

        self.receive_data_task: Optional[asyncio.Future] = None
        self.check_keep_alive_task: Optional[asyncio.Future] = None
        self.close_task: Optional[asyncio.Future] = None

        # We need to set an event loop here if there is none
        # Or else we will not be able to create an asyncio.Event()
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", message="There is no current event loop"
                )
                self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

        self._wait_closed: asyncio.Event = asyncio.Event()
        self._wait_closed.set()

        self._no_more_listeners: asyncio.Event = asyncio.Event()
        self._no_more_listeners.set()

        if self.keep_alive_timeout is not None:
            self._next_keep_alive_message: asyncio.Event = asyncio.Event()
            self._next_keep_alive_message.set()

        self._connecting: bool = False
        self._connected: bool = False

        self.close_exception: Optional[Exception] = None

    @property
    def response_headers(self) -> Dict[str, str]:
        return self.adapter.response_headers

    async def _initialize(self):
        """Hook to send the initialization messages after the connection
        and potentially wait for the backend ack.
        """
        pass  # pragma: no cover

    async def _stop_listener(self, query_id: int) -> None:
        """Hook to stop to listen to a specific query.
        Will send a stop message in some subclasses.
        """
        pass  # pragma: no cover

    async def _after_connect(self) -> None:
        """Hook to add custom code for subclasses after the connection
        has been established.
        """
        pass  # pragma: no cover

    async def _after_initialize(self) -> None:
        """Hook to add custom code for subclasses after the initialization
        has been done.
        """
        pass  # pragma: no cover

    async def _close_hook(self) -> None:
        """Hook to add custom code for subclasses for the connection close"""
        pass  # pragma: no cover

    async def _connection_terminate(self) -> None:
        """Hook to add custom code for subclasses after the initialization
        has been done.
        """
        pass  # pragma: no cover

    async def _send(self, message: str) -> None:
        """Send the provided message to the adapter connection and log the message"""

        if not self._connected:
            if isinstance(self.close_exception, TransportConnectionFailed):
                raise self.close_exception
            else:
                raise TransportConnectionFailed() from self.close_exception

        try:
            # Can raise TransportConnectionFailed
            await self.adapter.send(message)
            log.debug(">>> %s", message)
        except TransportConnectionFailed as e:
            await self._fail(e, clean_close=False)
            raise e

    async def _receive(self) -> str:
        """Wait the next message from the connection and log the answer"""

        # It is possible that the connection has been already closed in another task
        if not self._connected:
            raise TransportConnectionFailed() from self.close_exception

        # Wait for the next frame.
        # Can raise TransportConnectionFailed or TransportProtocolError
        answer: str = await self.adapter.receive()

        log.debug("<<< %s", answer)

        return answer

    @abstractmethod
    async def _send_query(
        self,
        request: GraphQLRequest,
    ) -> int:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def _parse_answer(
        self, answer: str
    ) -> Tuple[str, Optional[int], Optional[ExecutionResult]]:
        raise NotImplementedError  # pragma: no cover

    async def _check_ws_liveness(self) -> None:
        """Coroutine which will periodically check the liveness of the connection
        through keep-alive messages
        """

        try:
            while True:
                await asyncio.wait_for(
                    self._next_keep_alive_message.wait(), self.keep_alive_timeout
                )

                # Reset for the next iteration
                self._next_keep_alive_message.clear()

        except asyncio.TimeoutError:
            # No keep-alive message in the appriopriate interval, close with error
            # while trying to notify the server of a proper close (in case
            # the keep-alive interval of the client or server was not aligned
            # the connection still remains)

            # If the timeout happens during a close already in progress, do nothing
            if self.close_task is None:
                await self._fail(
                    TransportServerError(
                        "No keep-alive message has been received within "
                        "the expected interval ('keep_alive_timeout' parameter)"
                    ),
                    clean_close=False,
                )

        except asyncio.CancelledError:
            # The client is probably closing, handle it properly
            pass

    async def _receive_data_loop(self) -> None:
        """Main asyncio task which will listen to the incoming messages and will
        call the parse_answer and handle_answer methods of the subclass."""
        try:
            while True:

                # Wait the next answer from the server
                try:
                    answer = await self._receive()
                except (TransportConnectionFailed, TransportProtocolError) as e:
                    await self._fail(e, clean_close=False)
                    break

                # Parse the answer
                try:
                    answer_type, answer_id, execution_result = self._parse_answer(
                        answer
                    )
                except TransportQueryError as e:
                    # Received an exception for a specific query
                    # ==> Add an exception to this query queue
                    # The exception is raised for this specific query,
                    # but the transport is not closed.
                    assert isinstance(
                        e.query_id, int
                    ), "TransportQueryError should have a query_id defined here"
                    try:
                        await self.listeners[e.query_id].set_exception(e)
                    except KeyError:
                        # Do nothing if no one is listening to this query_id
                        pass

                    continue

                except (TransportServerError, TransportProtocolError) as e:
                    # Received a global exception for this transport
                    # ==> close the transport
                    # The exception will be raised for all current queries.
                    await self._fail(e, clean_close=False)
                    break

                await self._handle_answer(answer_type, answer_id, execution_result)

        finally:
            log.debug("Exiting _receive_data_loop()")

    async def _handle_answer(
        self,
        answer_type: str,
        answer_id: Optional[int],
        execution_result: Optional[ExecutionResult],
    ) -> None:

        try:
            # Put the answer in the queue
            if answer_id is not None:
                await self.listeners[answer_id].put((answer_type, execution_result))
        except KeyError:
            # Do nothing if no one is listening to this query_id.
            pass

    async def subscribe(
        self,
        request: GraphQLRequest,
        *,
        send_stop: Optional[bool] = True,
    ) -> AsyncGenerator[ExecutionResult, None]:
        """Send a query and receive the results using a python async generator.

        The query can be a graphql query, mutation or subscription.

        The results are sent as an ExecutionResult object.
        """

        # Send the query and receive the id
        query_id: int = await self._send_query(
            request,
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
                # This can raise TransportError or TransportConnectionFailed
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
            raise e

        finally:
            log.debug(f"In subscribe finally for query_id {query_id}")
            self._remove_listener(query_id)

    async def execute(
        self,
        request: GraphQLRequest,
    ) -> ExecutionResult:
        """Execute the provided request against the configured remote server
        using the current session.

        Send a query but close the async generator as soon as we have the first answer.

        The result is sent as an ExecutionResult object.
        """
        first_result = None

        generator = self.subscribe(
            request,
            send_stop=False,
        )

        async for result in generator:
            first_result = result
            break

        # Apparently, on pypy the GeneratorExit exception is not raised after a break
        # --> the clean_close has to time out
        # We still need to manually close the async generator
        await generator.aclose()

        if first_result is None:
            raise TransportQueryError(
                "Query completed without any answer received from the server"
            )

        return first_result

    async def connect(self) -> None:
        """Coroutine which will:

        - connect to the websocket address
        - send the init message
        - wait for the connection acknowledge from the server
        - create an asyncio task which will be used to receive
          and parse the answers

        Should be cleaned with a call to the close coroutine
        """

        log.debug("connect: starting")

        if not self._connected and not self._connecting:

            # Set connecting to True to avoid a race condition if user is trying
            # to connect twice using the same client at the same time
            self._connecting = True

            # Generate a TimeoutError if taking more than connect_timeout seconds
            # Set the _connecting flag to False after in all cases
            try:
                await asyncio.wait_for(
                    self.adapter.connect(),
                    self.connect_timeout,
                )
                self._connected = True
            finally:
                self._connecting = False

            # Run the after_connect hook of the subclass
            await self._after_connect()

            self.next_query_id = 1
            self.close_exception = None
            self._wait_closed.clear()

            # Send the init message and wait for the ack from the server
            # Note: This should generate a TimeoutError
            # if no ACKs are received within the ack_timeout
            try:
                await self._initialize()
            except TransportConnectionFailed as e:
                raise e
            except (
                TransportProtocolError,
                TransportServerError,
                asyncio.TimeoutError,
            ) as e:
                await self._fail(e, clean_close=False)
                raise e

            # Run the after_init hook of the subclass
            await self._after_initialize()

            # If specified, create a task to check liveness of the connection
            # through keep-alive messages
            if self.keep_alive_timeout is not None:
                self.check_keep_alive_task = asyncio.ensure_future(
                    self._check_ws_liveness()
                )

            # Create a task to listen to the incoming websocket messages
            self.receive_data_task = asyncio.ensure_future(self._receive_data_loop())

        else:
            raise TransportAlreadyConnected("Transport is already connected")

        log.debug("connect: done")

    def _remove_listener(self, query_id: int) -> None:
        """After exiting from a subscription, remove the listener and
        signal an event if this was the last listener for the client.
        """
        if query_id in self.listeners:
            del self.listeners[query_id]

        remaining = len(self.listeners)
        log.debug(f"listener {query_id} deleted, {remaining} remaining")

        if remaining == 0:
            self._no_more_listeners.set()

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
            assert self._connected

            # Saving exception to raise it later if trying to use the transport
            # after it has already closed.
            self.close_exception = e

            # Properly shut down liveness checker if enabled
            if self.check_keep_alive_task is not None:
                # More info: https://stackoverflow.com/a/43810272/1113207
                self.check_keep_alive_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self.check_keep_alive_task

            # Calling the subclass close hook
            await self._close_hook()

            if clean_close:
                log.debug("_close_coro: starting clean_close")
                try:
                    await self._clean_close(e)
                except Exception as exc:  # pragma: no cover
                    log.warning("Ignoring exception in _clean_close: " + repr(exc))

            if log.isEnabledFor(logging.DEBUG):
                log.debug(
                    f"_close_coro: sending exception to {len(self.listeners)} listeners"
                )

            # Send an exception to all remaining listeners
            for query_id, listener in self.listeners.items():
                await listener.set_exception(e)

            log.debug("_close_coro: close connection")

            await self.adapter.close()

            log.debug("_close_coro: connection closed")

        except Exception as exc:  # pragma: no cover
            log.warning("Exception catched in _close_coro: " + repr(exc))

        finally:

            log.debug("_close_coro: start cleanup")

            self._connected = False
            self.close_task = None
            self.check_keep_alive_task = None
            self._wait_closed.set()

        log.debug("_close_coro: exiting")

    async def _fail(self, e: Exception, clean_close: bool = True) -> None:
        if log.isEnabledFor(logging.DEBUG):
            import inspect

            current_frame = inspect.currentframe()
            assert current_frame is not None
            caller_frame = current_frame.f_back
            assert caller_frame is not None
            caller_name = inspect.getframeinfo(caller_frame).function
            log.debug(f"_fail from {caller_name}: " + repr(e))

        if self.close_task is None:

            if self._connected:
                self.close_task = asyncio.shield(
                    asyncio.ensure_future(self._close_coro(e, clean_close=clean_close))
                )
            else:
                log.debug("_fail started with self._connected:False -> already closed")
        else:
            log.debug(
                "close_task is not None in _fail. Previous exception is: "
                + repr(self.close_exception)
                + " New exception is: "
                + repr(e)
            )

    async def close(self) -> None:
        log.debug("close: starting")

        await self._fail(TransportClosed("Transport closed by user"))
        await self.wait_closed()

        log.debug("close: done")

    async def wait_closed(self) -> None:
        log.debug("wait_close: starting")

        try:
            await asyncio.wait_for(self._wait_closed.wait(), self.close_timeout)
        except asyncio.TimeoutError:
            log.warning("Timer close_timeout fired in wait_closed")

        log.debug("wait_close: done")

    @property
    def url(self) -> str:
        return self.adapter.url

    @property
    def connect_args(self) -> Dict[str, Any]:
        return self.adapter.connect_args
