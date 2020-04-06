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


@six.add_metaclass(abc.ABCMeta)
class AsyncTransport(Transport):
    @abc.abstractmethod
    async def connect(self):
        """Coroutine used to create a connection to the specified address
        """
        raise NotImplementedError(
            "Any AsyncTransport subclass must implement execute method"
        )

    @abc.abstractmethod
    async def close(self):
        """Coroutine used to Close an established connection
        """
        raise NotImplementedError(
            "Any AsyncTransport subclass must implement execute method"
        )

    @abc.abstractmethod
    async def execute(self, document, variable_values=None, operation_name=None):
        """Execute the provided document AST for either a remote or local GraphQL Schema.
        """
        raise NotImplementedError(
            "Any AsyncTransport subclass must implement execute method"
        )

    @abc.abstractmethod
    async def subscribe(self, document, variable_values=None, operation_name=None):
        """Send a query and receive the results using an async generator

        The query can be a graphql query, mutation or subscription

        The results are sent as an ExecutionResult object
        """
        raise NotImplementedError(
            "Any AsyncTransport subclass must implement execute method"
        )
