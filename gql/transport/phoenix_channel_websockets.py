import asyncio
import json
import logging
from typing import Any, Dict, Optional, Tuple

from graphql import DocumentNode, ExecutionResult, print_ast
from websockets.exceptions import ConnectionClosed

from .exceptions import (
    TransportProtocolError,
    TransportQueryError,
    TransportServerError,
)
from .websockets import WebsocketsTransport

log = logging.getLogger(__name__)


class Subscription:
    """Records listener_id and unsubscribe query_id for a subscription."""

    def __init__(self, query_id: int) -> None:
        self.listener_id: int = query_id
        self.unsubscribe_id: Optional[int] = None


class PhoenixChannelWebsocketsTransport(WebsocketsTransport):
    """The PhoenixChannelWebsocketsTransport is an **EXPERIMENTAL** async transport
    which allows you to execute queries and subscriptions against an `Absinthe`_
    backend using the `Phoenix`_ framework `channels`_.

    .. _Absinthe: http://absinthe-graphql.org
    .. _Phoenix: https://www.phoenixframework.org
    .. _channels: https://hexdocs.pm/phoenix/Phoenix.Channel.html#content
    """

    def __init__(
        self,
        channel_name: str = "__absinthe__:control",
        heartbeat_interval: float = 30,
        *args,
        **kwargs,
    ) -> None:
        """Initialize the transport with the given parameters.

        :param channel_name: Channel on the server this transport will join.
            The default for Absinthe servers is "__absinthe__:control"
        :param heartbeat_interval: Interval in second between each heartbeat messages
            sent by the client
        """
        self.channel_name: str = channel_name
        self.heartbeat_interval: float = heartbeat_interval
        self.heartbeat_task: Optional[asyncio.Future] = None
        self.subscriptions: Dict[str, Subscription] = {}
        super(PhoenixChannelWebsocketsTransport, self).__init__(*args, **kwargs)

    async def _send_init_message_and_wait_ack(self) -> None:
        """Join the specified channel and wait for the connection ACK.

        If the answer is not a connection_ack message, we will return an Exception.
        """

        query_id = self.next_query_id
        self.next_query_id += 1

        init_message = json.dumps(
            {
                "topic": self.channel_name,
                "event": "phx_join",
                "payload": {},
                "ref": query_id,
            }
        )

        await self._send(init_message)

        # Wait for the connection_ack message or raise a TimeoutError
        init_answer = await asyncio.wait_for(self._receive(), self.ack_timeout)

        answer_type, answer_id, execution_result = self._parse_answer(init_answer)

        if answer_type != "reply":
            raise TransportProtocolError(
                "Websocket server did not return a connection ack"
            )

        async def heartbeat_coro():
            while True:
                await asyncio.sleep(self.heartbeat_interval)
                try:
                    query_id = self.next_query_id
                    self.next_query_id += 1

                    await self._send(
                        json.dumps(
                            {
                                "topic": "phoenix",
                                "event": "heartbeat",
                                "payload": {},
                                "ref": query_id,
                            }
                        )
                    )
                except ConnectionClosed:  # pragma: no cover
                    return

        self.heartbeat_task = asyncio.ensure_future(heartbeat_coro())

    async def _send_stop_message(self, query_id: int) -> None:
        """Send an 'unsubscribe' message to the Phoenix Channel referencing
        the listener's query_id, saving the query_id of the message.

        The server should afterwards return a 'phx_reply' message with
        the same query_id and subscription_id of the 'unsubscribe' request.
        """
        subscription_id = self._find_subscription_id(query_id)

        unsubscribe_query_id = self.next_query_id
        self.next_query_id += 1

        # Save the ref so it can be matched in the reply
        self.subscriptions[subscription_id].unsubscribe_id = unsubscribe_query_id
        unsubscribe_message = json.dumps(
            {
                "topic": self.channel_name,
                "event": "unsubscribe",
                "payload": {"subscriptionId": subscription_id},
                "ref": unsubscribe_query_id,
            }
        )

        await self._send(unsubscribe_message)

    async def _send_connection_terminate_message(self) -> None:
        """Send a phx_leave message to disconnect from the provided channel."""

        query_id = self.next_query_id
        self.next_query_id += 1

        connection_terminate_message = json.dumps(
            {
                "topic": self.channel_name,
                "event": "phx_leave",
                "payload": {},
                "ref": query_id,
            }
        )

        await self._send(connection_terminate_message)

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

        query_str = json.dumps(
            {
                "topic": self.channel_name,
                "event": "doc",
                "payload": {
                    "query": print_ast(document),
                    "variables": variable_values or {},
                },
                "ref": query_id,
            }
        )

        await self._send(query_str)

        return query_id

    def _parse_answer(
        self, answer: str
    ) -> Tuple[str, Optional[int], Optional[ExecutionResult]]:
        """Parse the answer received from the server

        Returns a list consisting of:
            - the answer_type (between:
              'heartbeat', 'data', 'reply', 'error', 'unsubscribe')
            - the answer id (Integer) if received or None
            - an execution Result if the answer_type is 'data' or None
        """

        event: str = ""
        answer_id: Optional[int] = None
        answer_type: str = ""
        execution_result: Optional[ExecutionResult] = None

        try:
            json_answer = json.loads(answer)

            event = str(json_answer.get("event"))

            if event == "subscription:data":
                payload = json_answer.get("payload")

                if not isinstance(payload, dict):
                    raise ValueError("payload is not a dict")

                subscription_id = str(payload.get("subscriptionId"))
                try:
                    answer_id = self.subscriptions[subscription_id].listener_id
                except KeyError:
                    raise ValueError(
                        f"subscription '{subscription_id}' has not been registered"
                    )

                result = payload.get("result")

                if not isinstance(result, dict):
                    raise ValueError("result is not a dict")

                answer_type = "data"

                execution_result = ExecutionResult(
                    data=result.get("data"),
                    errors=result.get("errors"),
                    extensions=result.get("extensions"),
                )

            elif event == "phx_reply":
                try:
                    answer_id = int(json_answer.get("ref"))
                except Exception:
                    raise ValueError("ref is not an integer")

                if answer_id == 0:
                    raise ValueError("ref is zero")

                payload = json_answer.get("payload")

                if not isinstance(payload, dict):
                    raise ValueError("payload is not a dict")

                status = str(payload.get("status"))

                if status == "ok":
                    # join or leave answer
                    answer_type = "reply"

                    response = payload.get("response")

                    if isinstance(response, dict):
                        if "data" in response:
                            # query or mutation result answer
                            answer_type = "data"

                            execution_result = ExecutionResult(
                                data=response["data"],
                                errors=response.get("errors"),
                                extensions=response.get("extensions"),
                            )
                        elif "subscriptionId" in response:
                            # subscribe or unsubscribe answer
                            subscription_id = str(response.get("subscriptionId"))

                            # answer_type is "reply" or "unsubscribe"
                            answer_type, answer_id = self._parse_subscription_answer(
                                answer_id, subscription_id
                            )

                elif status == "error":
                    response = payload.get("response")

                    if isinstance(response, dict):
                        if "errors" in response:
                            raise TransportQueryError(
                                str(response.get("errors")), query_id=answer_id
                            )
                        elif "reason" in response:
                            raise TransportQueryError(
                                str(response.get("reason")), query_id=answer_id
                            )
                    raise ValueError("reply error")

                elif status == "timeout":
                    raise TransportQueryError("reply timeout", query_id=answer_id)

            elif event == "phx_error":
                # Sent if the channel has crashed
                # answer_id will be the "join_ref" for the channel
                # answer_id = int(json_answer.get("ref"))
                raise TransportServerError("Server error")
            elif event == "phx_close":
                answer_type = "close"
            else:
                raise ValueError

        except ValueError as e:
            log.error(f"Error parsing answer '{answer}' " + repr(e))
            raise TransportProtocolError(
                "Server did not return a GraphQL result"
            ) from e

        return answer_type, answer_id, execution_result

    def _parse_subscription_answer(
        self, answer_id: int, subscription_id: str
    ) -> Tuple[str, int]:
        if subscription_id in self.subscriptions:
            # Unsubscribe reply
            subscription = self.subscriptions[subscription_id]
            unsubscribe_id = subscription.unsubscribe_id
            if unsubscribe_id is None or unsubscribe_id != answer_id:
                raise TransportProtocolError(
                    "Unsubscription reply does not match an request"
                )

            answer_id = subscription.listener_id
            answer_type = "unsubscribe"
        else:
            # Subscription reply
            self.subscriptions[subscription_id] = Subscription(answer_id)

            # Confirm unsubscribe for subscriptions
            self.listeners[answer_id].send_stop = True

            answer_type = "reply"

        return answer_type, answer_id

    async def _handle_answer(
        self,
        answer_type: str,
        answer_id: Optional[int],
        execution_result: Optional[ExecutionResult],
    ) -> None:
        if answer_type == "close":
            await self.close()
        elif answer_type == "unsubscribe":
            # Remove the listener here, to possibly signal
            # that it is the last listener in the session.
            self._remove_listener(answer_id)
        else:
            await super()._handle_answer(answer_type, answer_id, execution_result)

    def _remove_listener(self, query_id) -> None:
        try:
            subscription_id = self._find_subscription_id(query_id)
            del self.subscriptions[subscription_id]
        except Exception:
            pass
        super()._remove_listener(query_id)

    def _find_subscription_id(self, query_id: int) -> str:
        """Perform a reverse lookup to find the subscription id matching
        a listener's query_id.
        """
        for subscription_id, subscription in self.subscriptions.items():
            if subscription.listener_id == query_id:
                return subscription_id

        raise TransportProtocolError(
            f"No subscription matches listener {query_id}"
        )  # pragma: no cover

    async def _close_coro(self, e: Exception, clean_close: bool = True) -> None:
        if self.heartbeat_task is not None:
            self.heartbeat_task.cancel()

        await super()._close_coro(e, clean_close)
