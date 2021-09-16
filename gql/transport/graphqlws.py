import json
import logging
from typing import Any, Dict, Optional, Tuple, cast

from graphql import DocumentNode, ExecutionResult, print_ast
from websockets.typing import Subprotocol

from .exceptions import TransportProtocolError, TransportQueryError
from .websockets import WebsocketsTransport

log = logging.getLogger(__name__)


class GraphQLWSTransport(WebsocketsTransport):
    """This transport is an async transport implementing the `graphql-ws`_ protocol.

    .. _graphql-ws: https://github.com/enisdenjo/graphql-ws/blob/master/PROTOCOL.md
    """

    def __init__(self, *args, **kwargs,) -> None:
        """Initialize the transport with the given parameters.
        """
        super().__init__(*args, **kwargs)
        self.subprotocol: Subprotocol = cast(Subprotocol, "graphql-transport-ws")

    async def _send_stop_message(self, query_id: int) -> None:
        """In the graphql-ws protocol, the client needs to send a "complete"
        message instead of a "stop" message.

        The server should afterwards return a 'complete' message.
        """

        stop_message = json.dumps({"id": str(query_id), "type": "complete"})

        await self._send(stop_message)

    async def _send_connection_terminate_message(self) -> None:
        """There is no "connection_terminate" message in the graphql-ws protocol."""

        pass

    async def _send_query(
        self,
        document: DocumentNode,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
    ) -> int:
        """Send a query to the provided websocket connection.

        We use an incremented id to reference the query.

        Returns the used id for this query.

        In the graphql-ws protocol, the type is _subscribe_ instead of _start_
        """

        query_id = self.next_query_id
        self.next_query_id += 1

        payload: Dict[str, Any] = {"query": print_ast(document)}
        if variable_values:
            payload["variables"] = variable_values
        if operation_name:
            payload["operationName"] = operation_name

        query_str = json.dumps(
            {"id": str(query_id), "type": "subscribe", "payload": payload}
        )

        await self._send(query_str)

        return query_id

    def _parse_answer(
        self, answer: str
    ) -> Tuple[str, Optional[int], Optional[ExecutionResult]]:
        """Parse the answer received from the server

        Returns a list consisting of:
            - the answer_type (between:
              'connection_ack', 'ping', 'pong', 'data', 'error', 'complete')
            - the answer id (Integer) if received or None
            - an execution Result if the answer_type is 'data' or None

        Differences with the apollo websockets protocol (superclass):
            - the "data" message is now called "next"
            - the "stop" message is now called "complete"
            - there is no connection_terminate or connection_error messages
            - instead of a unidirectional keep-alive (ka) message from server to client,
              there is now the possibility to send bidirectional ping/pong messages
            - connection_ack has an optional payload
        """

        answer_type: str = ""
        answer_id: Optional[int] = None
        execution_result: Optional[ExecutionResult] = None

        try:
            json_answer = json.loads(answer)

            answer_type = str(json_answer.get("type"))

            if answer_type in ["next", "error", "complete"]:
                answer_id = int(str(json_answer.get("id")))

                if answer_type == "next" or answer_type == "error":

                    payload = json_answer.get("payload")

                    if not isinstance(payload, dict):
                        raise ValueError("payload is not a dict")

                    if answer_type == "next":

                        if "errors" not in payload and "data" not in payload:
                            raise ValueError(
                                "payload does not contain 'data' or 'errors' fields"
                            )

                        execution_result = ExecutionResult(
                            errors=payload.get("errors"),
                            data=payload.get("data"),
                            extensions=payload.get("extensions"),
                        )

                        # Saving answer_type as 'data' to be understood with superclass
                        answer_type = "data"

                    elif answer_type == "error":

                        raise TransportQueryError(
                            str(payload), query_id=answer_id, errors=[payload]
                        )

            elif answer_type in ["ping", "pong", "connection_ack"]:
                # TODO: do something with the payloads here ?
                # payload = json_answer.get("payload")
                pass

            else:
                raise ValueError

        except ValueError as e:
            raise TransportProtocolError(
                f"Server did not return a GraphQL result: {answer}"
            ) from e

        return answer_type, answer_id, execution_result
