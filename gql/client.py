import asyncio
from inspect import isawaitable
from typing import Any, AsyncGenerator, Dict, Generator, Optional, Union, cast

from graphql import (
    DocumentNode,
    ExecutionResult,
    GraphQLSchema,
    build_ast_schema,
    build_client_schema,
    get_introspection_query,
    parse,
    validate,
)

from .transport.async_transport import AsyncTransport
from .transport.exceptions import TransportQueryError
from .transport.local_schema import LocalSchemaTransport
from .transport.transport import Transport


class Client:
    def __init__(
        self,
        schema: Optional[GraphQLSchema] = None,
        introspection=None,
        type_def: Optional[str] = None,
        transport: Optional[Union[Transport, AsyncTransport]] = None,
        fetch_schema_from_transport: bool = False,
        execute_timeout: Optional[int] = 10,
    ):
        assert not (
            type_def and introspection
        ), "Cannot provide introspection type definition at the same time."
        if transport and fetch_schema_from_transport:
            assert (
                not schema
            ), "Cannot fetch the schema from transport if is already provided."
        if introspection:
            assert (
                not schema
            ), "Cannot provide introspection and schema at the same time."
            schema = build_client_schema(introspection)
        elif type_def:
            assert (
                not schema
            ), "Cannot provide type definition and schema at the same time."
            type_def_ast = parse(type_def)
            schema = build_ast_schema(type_def_ast)
        elif schema and not transport:
            transport = LocalSchemaTransport(schema)

        # GraphQL schema
        self.schema: Optional[GraphQLSchema] = schema

        # Answer of the introspection query
        self.introspection = introspection

        # GraphQL transport chosen
        self.transport: Optional[Union[Transport, AsyncTransport]] = transport

        # Flag to indicate that we need to fetch the schema from the transport
        # On async transports, we fetch the schema before executing the first query
        self.fetch_schema_from_transport: bool = fetch_schema_from_transport

        # Enforced timeout of the execute function
        self.execute_timeout = execute_timeout

        if isinstance(transport, Transport) and fetch_schema_from_transport:
            with self as session:
                session.fetch_schema()

    def validate(self, document):
        if not self.schema:
            raise Exception(
                "Cannot validate the document locally, you need to pass a schema."
            )
        validation_errors = validate(self.schema, document)
        if validation_errors:
            raise validation_errors[0]

    def execute_sync(self, document: DocumentNode, *args, **kwargs) -> Dict:
        with self as session:
            return session.execute(document, *args, **kwargs)

    async def execute_async(self, document: DocumentNode, *args, **kwargs) -> Dict:
        async with self as session:
            return await session.execute(document, *args, **kwargs)

    def execute(self, document: DocumentNode, *args, **kwargs) -> Dict:
        """Execute the provided document AST against the configured remote server.

        This function WILL BLOCK until the result is received from the server.

        Either the transport is sync and we execute the query synchronously directly
        OR the transport is async and we execute the query in the asyncio loop
        (blocking here until answer).
        """

        if isinstance(self.transport, AsyncTransport):

            loop = asyncio.get_event_loop()

            assert not loop.is_running(), (
                "Cannot run client.execute if an asyncio loop is running."
                " Use execute_async instead."
            )

            data: Dict[Any, Any] = loop.run_until_complete(
                self.execute_async(document, *args, **kwargs)
            )

            return data

        else:  # Sync transports
            return self.execute_sync(document, *args, **kwargs)

    async def subscribe_async(
        self, document: DocumentNode, *args, **kwargs
    ) -> AsyncGenerator[Dict, None]:
        async with self as session:

            self._generator: AsyncGenerator[Dict, None] = session.subscribe(
                document, *args, **kwargs
            )

            async for result in self._generator:
                yield result

    def subscribe(
        self, document: DocumentNode, *args, **kwargs
    ) -> Generator[Dict, None, None]:
        """Execute a GraphQL subscription with a python generator.

        We need an async transport for this functionality.
        """

        async_generator = self.subscribe_async(document, *args, **kwargs)

        loop = asyncio.get_event_loop()

        assert not loop.is_running(), (
            "Cannot run client.subscribe if an asyncio loop is running."
            " Use subscribe_async instead."
        )

        try:
            while True:
                result = loop.run_until_complete(async_generator.__anext__())
                yield result

        except StopAsyncIteration:
            pass

    async def __aenter__(self):

        assert isinstance(
            self.transport, AsyncTransport
        ), "Only a transport of type AsyncTransport can be used asynchronously"

        await self.transport.connect()

        if not hasattr(self, "session"):
            self.session = AsyncClientSession(client=self)

        return self.session

    async def __aexit__(self, exc_type, exc, tb):

        await self.transport.close()

    def __enter__(self):

        assert not isinstance(
            self.transport, AsyncTransport
        ), "Only a sync transport can be use. Use 'async with Client(...)' instead"

        self.transport.connect()

        if not hasattr(self, "session"):
            self.session = SyncClientSession(client=self)

        return self.session

    def __exit__(self, *args):
        self.transport.close()


class SyncClientSession:
    """An instance of this class is created when using 'with' on the client.

    It contains the sync method execute to send queries
    with the sync transports.
    """

    def __init__(self, client: Client):
        self.client = client

    def execute(self, document: DocumentNode, *args, **kwargs) -> Dict:

        # Validate document
        if self.client.schema:
            self.client.validate(document)

        result = self.transport.execute(document, *args, **kwargs)

        assert not isawaitable(result), "Transport returned an awaitable result."
        result = cast(ExecutionResult, result)

        if result.errors:
            raise TransportQueryError(str(result.errors[0]))

        assert (
            result.data is not None
        ), "Transport returned an ExecutionResult without data or errors"

        return result.data

    def fetch_schema(self) -> None:
        execution_result = self.transport.execute(parse(get_introspection_query()))
        self.client.introspection = execution_result.data
        self.client.schema = build_client_schema(self.client.introspection)

    @property
    def transport(self):
        return self.client.transport


class AsyncClientSession:
    """An instance of this class is created when using 'async with' on the client.

    It contains the async methods (execute, subscribe) to send queries
    with the async transports.
    """

    def __init__(self, client: Client):
        self.client = client

    async def fetch_and_validate(self, document: DocumentNode):
        """Fetch schema from transport if needed and validate document.

        If no schema is present, the validation will be skipped.
        """

        # Get schema from transport if needed
        if self.client.fetch_schema_from_transport and not self.client.schema:
            await self.fetch_schema()

        # Validate document
        if self.client.schema:
            self.client.validate(document)

    async def subscribe(
        self, document: DocumentNode, *args, **kwargs
    ) -> AsyncGenerator[Dict, None]:

        # Fetch schema from transport if needed and validate document if possible
        await self.fetch_and_validate(document)

        # Subscribe to the transport and yield data or raise error
        self._generator: AsyncGenerator[
            ExecutionResult, None
        ] = self.transport.subscribe(document, *args, **kwargs)

        async for result in self._generator:
            if result.errors:
                # Note: we need to run generator.aclose() here or the finally block in
                # transport.subscribe will not be reached in pypy3 (py 3.6.1)
                await self._generator.aclose()

                raise TransportQueryError(str(result.errors[0]))

            elif result.data is not None:
                yield result.data

    async def execute(self, document: DocumentNode, *args, **kwargs) -> Dict:

        # Fetch schema from transport if needed and validate document if possible
        await self.fetch_and_validate(document)

        # Execute the query with the transport with a timeout
        result = await asyncio.wait_for(
            self.transport.execute(document, *args, **kwargs),
            self.client.execute_timeout,
        )

        # Raise an error if an error is returned in the ExecutionResult object
        if result.errors:
            raise TransportQueryError(str(result.errors[0]))

        return result.data

    async def fetch_schema(self) -> None:
        execution_result = await self.transport.execute(
            parse(get_introspection_query())
        )
        self.client.introspection = execution_result.data
        self.client.schema = build_client_schema(self.client.introspection)

    @property
    def transport(self):
        return self.client.transport
