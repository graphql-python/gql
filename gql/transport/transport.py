import abc
from typing import Any, Dict, List

from graphql import ExecutionResult, print_ast

from ..graphql_request import GraphQLRequest


class Transport(abc.ABC):
    @abc.abstractmethod
    def execute(
        self,
        request: GraphQLRequest,
        *args: Any,
        **kwargs: Any,
    ) -> ExecutionResult:
        """Execute GraphQL query.

        Execute the provided request for either a remote or local GraphQL Schema.

        :param request: GraphQL request as a GraphQLRequest object.
        :return: ExecutionResult
        """
        raise NotImplementedError(
            "Any Transport subclass must implement execute method"
        )  # pragma: no cover

    def execute_batch(
        self,
        reqs: List[GraphQLRequest],
        *args: Any,
        **kwargs: Any,
    ) -> List[ExecutionResult]:
        """Execute multiple GraphQL requests in a batch.

        Execute the provided requests for either a remote or local GraphQL Schema.

        :param reqs: GraphQL requests as a list of GraphQLRequest objects.
        :return: a list of ExecutionResult objects
        """
        raise NotImplementedError(
            "This Transport has not implemented the execute_batch method"
        )

    def connect(self):
        """Establish a session with the transport."""
        pass  # pragma: no cover

    def close(self):
        """Close the transport

        This method doesn't have to be implemented unless the transport would benefit
        from it. This is currently used by the RequestsHTTPTransport transport to close
        the session's connection pool.
        """
        pass  # pragma: no cover

    def _build_payload(self, req: GraphQLRequest) -> Dict[str, Any]:
        query_str = print_ast(req.document)
        payload: Dict[str, Any] = {"query": query_str}

        if req.operation_name:
            payload["operationName"] = req.operation_name

        if req.variable_values:
            payload["variables"] = req.variable_values

        return payload
