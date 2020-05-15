from typing import Awaitable, Union

from graphql import DocumentNode, ExecutionResult, GraphQLSchema, execute

from gql.transport import Transport


class LocalSchemaTransport(Transport):
    """A transport for executing GraphQL queries against a local schema."""

    def __init__(
        self, schema: GraphQLSchema,
    ):
        """Initialize the transport with the given local schema.

        :param schema: Local schema as GraphQLSchema object
        """
        self.schema = schema

    def execute(
        self, document: DocumentNode, *args, **kwargs
    ) -> Union[ExecutionResult, Awaitable[ExecutionResult]]:
        """Execute the given document against the configured local schema.

        :param document: GraphQL query as AST Node object.
        :param args: Positional options for execute method from graphql-core.
        :param kwargs: Keyword options passed to execute method from graphql-core.
        :return: ExecutionResult (either as value or awaitable)
        """
        return execute(self.schema, document, *args, **kwargs)
