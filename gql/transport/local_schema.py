from inspect import isawaitable
from typing import AsyncGenerator, Awaitable, cast

from graphql import GraphQLSchema, execute, subscribe
from graphql.execution import ExecutionResult
from graphql.language.ast import Document as DocumentNode

from gql.transport import AsyncTransport


class LocalSchemaTransport(AsyncTransport):
    """A transport for executing GraphQL queries against a local schema."""

    def __init__(
        self, schema: GraphQLSchema,
    ):
        """Initialize the transport with the given local schema.

        :param schema: Local schema as GraphQLSchema object
        """
        self.schema = schema

    async def connect(self):
        """No connection needed on local transport
        """
        pass

    async def close(self):
        """No close needed on local transport
        """
        pass

    async def execute(
        self, document: DocumentNode, *args, **kwargs,
    ) -> ExecutionResult:
        """Execute the provided document AST for on a local GraphQL Schema.
        """

        result_or_awaitable = execute(self.schema, document, *args, **kwargs)

        execution_result: ExecutionResult

        if isawaitable(result_or_awaitable):
            awaitable = cast(Awaitable[ExecutionResult], result_or_awaitable)
            execution_result = await awaitable
        else:
            result = cast(ExecutionResult, result_or_awaitable)
            execution_result = result

        return execution_result

    async def subscribe(
        self, document: DocumentNode, *args, **kwargs,
    ) -> AsyncGenerator[ExecutionResult, None]:
        """Send a subscription and receive the results using an async generator

        The results are sent as an ExecutionResult object
        """

        subscribe_result = subscribe(self.schema, document, *args, **kwargs)

        if isinstance(subscribe_result, ExecutionResult):
            yield subscribe_result

        else:
            async for result in subscribe_result:
                yield result
