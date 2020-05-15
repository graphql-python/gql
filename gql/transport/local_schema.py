from graphql import GraphQLSchema
from graphql.execution import ExecutionResult, execute
from graphql.language.ast import DocumentNode

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

    def execute(self, document: DocumentNode, *args, **kwargs) -> ExecutionResult:
        """Execute the given document against the configured local schema.

        :param document: GraphQL query as AST Node object.
        :param args: Positional options for execute method from graphql-core library.
        :param kwargs: Keyword options passed to execute method from graphql-core library.
        :return: Either ExecutionResult or a Promise that resolves to ExecutionResult object.
        """
        return execute(self.schema, document, *args, **kwargs)  # type: ignore
