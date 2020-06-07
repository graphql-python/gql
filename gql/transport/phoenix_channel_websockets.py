import asyncio
import json
from typing import Dict, Optional, Tuple

from graphql import DocumentNode, ExecutionResult, print_ast

from .exceptions import (
    TransportProtocolError,
    TransportQueryError,
    TransportServerError,
)
from .websockets import WebsocketsTransport


class PhoenixChannelWebsocketsTransport(WebsocketsTransport):
    def __init__(
        self, channel_name: str, heartbeat_interval: int = 30, *args, **kwargs
    ) -> None:
        self.channel_name = channel_name
        self.heartbeat_interval = heartbeat_interval
        self.subscription_ids_to_query_ids: Dict[str, int] = {}
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
                await self._send(json.dumps({"topic": "phoenix", "event": "heartbeat"}))

        self.heartbeat_task = asyncio.ensure_future(heartbeat_coro())

    async def _send_stop_message(self, query_id: int) -> None:
        pass

    async def _send_connection_terminate_message(self) -> None:
        """Send a phx_leave message to disconnect from the provided channel.
        """

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
        variable_values: Optional[Dict[str, str]] = None,
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
              'heartbeat', 'data', 'reply', 'error', 'close')
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
                answer_id = self.subscription_ids_to_query_ids[subscription_id]
                result = payload.get("result")

                if not isinstance(result, dict):
                    raise ValueError("result is not a dict")

                answer_type = "data"

                execution_result = ExecutionResult(
                    errors=payload.get("errors"), data=result.get("data")
                )

            elif event == "phx_reply":
                answer_id = int(json_answer.get("ref"))
                payload = json_answer.get("payload")

                if not isinstance(payload, dict):
                    raise ValueError("payload is not a dict")

                status = str(payload.get("status"))

                if status == "ok":

                    answer_type = "reply"
                    response = payload.get("response")

                    if isinstance(response, dict) and "subscriptionId" in response:
                        subscription_id = str(response.get("subscriptionId"))
                        self.subscription_ids_to_query_ids[subscription_id] = answer_id

                elif status == "error":
                    response = payload.get("response")

                    if isinstance(response, dict):
                        raise TransportQueryError(
                            response.get("reason"), query_id=answer_id
                        )
                    else:
                        raise ValueError("reply error")

                elif status == "timeout":
                    raise ValueError("reply timeout")

            elif event == "phx_error":
                raise TransportServerError("Server error")
            elif event == "phx_close":
                answer_type = "close"
            else:
                raise ValueError

        except ValueError as e:
            raise TransportProtocolError(
                "Server did not return a GraphQL result"
            ) from e

        return answer_type, answer_id, execution_result

    async def _handle_answer(
        self,
        answer_type: str,
        answer_id: Optional[int],
        execution_result: Optional[ExecutionResult],
    ) -> None:
        if answer_type == "close":
            for listener in self.listeners.values():
                await listener.put(("complete", execution_result))
        else:
            await super()._handle_answer(answer_type, answer_id, execution_result)

    async def close(self) -> None:
        self.heartbeat_task.cancel()
        await super().close()
