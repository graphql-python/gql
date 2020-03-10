from typing import Union, Any

from graphql import GraphQLSchema
from graphql.execution import execute, ExecutionResult
from graphql.language.ast import Document
from promise import Promise

from gql.transport.transport import Transport


class LocalSchemaTransport(Transport):
    def __init__(
        self,  # type: LocalSchemaTransport
        schema  # type: GraphQLSchema
    ):
        """Create a HTTPTransport using requests library to execute GraphQL queries on local server.

        :param schema: Local schema as GraphQLSchema object
        """
        self.schema = schema

    def execute(self, document, *args, **kwargs):
        # type: (Document, Any, Any) -> Union[ExecutionResult, Promise[ExecutionResult]]
        """Execute the provided document AST for the provided local server.

        :param document: GraphQL query as AST Node object.
        :param args: Positional options for execute method from graphql-core library.
        :param kwargs: Keyword options passed to execute method from graphql-core library.
        :return: Either ExecutionResult or a Promise that resolves to ExecutionResult object.
        """
        return execute(
            self.schema,
            document,
            *args,
            **kwargs
        )
