import abc

from graphql import DocumentNode, ExecutionResult


class Transport:
    @abc.abstractmethod
    def execute(self, document: DocumentNode, *args, **kwargs) -> ExecutionResult:
        """Execute GraphQL query.

        Execute the provided document AST for either a remote or local GraphQL Schema.

        :param document: GraphQL query as AST Node or Document object.
        :return: ExecutionResult
        """
        raise NotImplementedError(
            "Any Transport subclass must implement execute method"
        )  # pragma: no cover

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
