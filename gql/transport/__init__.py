import abc
from typing import Union

import six
from graphql.execution import ExecutionResult
from graphql.language.ast import Node, Document
from promise import Promise


@six.add_metaclass(abc.ABCMeta)
class Transport:
    @abc.abstractmethod
    def execute(self, document):
        # type: (Union[Node, Document]) -> Union[ExecutionResult, Promise[ExecutionResult]]
        """Execute the provided document AST for either a remote or local GraphQL Schema.

        :param document: GraphQL query as AST Node or Document object.
        :return: Either ExecutionResult or a Promise that resolves to ExecutionResult object.
        """
        raise NotImplementedError("Any Transport subclass must implement execute method")
