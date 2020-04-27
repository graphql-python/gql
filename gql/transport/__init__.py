import abc
from typing import Union

import six
from graphql.execution import ExecutionResult
from graphql.language.ast import Document
from promise import Promise


@six.add_metaclass(abc.ABCMeta)
class Transport:
    @abc.abstractmethod
    def execute(self, document):
        # type: (Document) -> Union[ExecutionResult, Promise[ExecutionResult]]
        """Execute the provided document AST for either a remote or local GraphQL Schema.

        :param document: GraphQL query as AST Node or Document object.
        :return: Either ExecutionResult or a Promise that resolves to ExecutionResult object.
        """
        raise NotImplementedError(
            "Any Transport subclass must implement execute method"
        )

    def close(self):
        """Close the transport

        This method doesn't have to be implemented unless the transport would benefit from it.
        This is currently used by the RequestsHTTPTransport transport to close the session's
        connection pool.
        """
        pass
