from inspect import isawaitable
from typing import Any, AsyncGenerator, AsyncIterator, Awaitable, Coroutine, cast

from graphql import DocumentNode, ExecutionResult, GraphQLSchema, execute, subscribe

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
            result_or_awaitable = cast(Awaitable[ExecutionResult], result_or_awaitable)
            execution_result = await result_or_awaitable
        else:
            result_or_awaitable = cast(ExecutionResult, result_or_awaitable)
            execution_result = result_or_awaitable

        return execution_result

    async def subscribe(
        self, document: DocumentNode, *args, **kwargs,
    ) -> AsyncGenerator[ExecutionResult, None]:
        """Send a query and receive the results using an async generator

        The query can be a graphql query, mutation or subscription

        The results are sent as an ExecutionResult object
        """

        subscribe_result = subscribe(self.schema, document, *args, **kwargs)

        if isinstance(subscribe_result, ExecutionResult):
            yield ExecutionResult

        else:
            # if we don't get an ExecutionResult, then we should receive
            # a Coroutine returning an AsyncIterator[ExecutionResult]

            subscribe_coro = cast(
                Coroutine[Any, Any, AsyncIterator[ExecutionResult]], subscribe_result
            )

            subscribe_generator = await subscribe_coro

            async for result in subscribe_generator:
                yield result
