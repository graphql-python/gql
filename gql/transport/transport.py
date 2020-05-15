import abc
from typing import Awaitable, Union

from graphql import DocumentNode, ExecutionResult


class Transport:
    @abc.abstractmethod
    def execute(
        self, document: DocumentNode, *args, **kwargs
    ) -> Union[ExecutionResult, Awaitable[ExecutionResult]]:
        """Execute GraphQL query.

        Execute the provided document AST for either a remote or local GraphQL Schema.

        :param document: GraphQL query as AST Node or Document object.
        :return: ExecutionResult (either as value or awaitable)
        """
        raise NotImplementedError(
            "Any Transport subclass must implement execute method"
        )  # pragma: no cover

    def close(self):
        """Close the transport

        This method doesn't have to be implemented unless the transport would benefit
        from it. This is currently used by the RequestsHTTPTransport transport to close
        the session's connection pool.
        """
        pass
