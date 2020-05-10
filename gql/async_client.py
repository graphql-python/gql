import asyncio

from graphql import build_ast_schema, build_client_schema, introspection_query, parse
from graphql.execution import ExecutionResult
from graphql.language.ast import Document

from typing import Generator, AsyncGenerator, Dict, Any, cast

from .transport.local_schema import LocalSchemaTransport
from .transport.async_transport import AsyncTransport
from .transport.exceptions import TransportQueryError
from .client import Client


class AsyncClient(Client):
    def __init__(
        self,
        schema=None,
        introspection=None,
        type_def=None,
        transport=None,
        fetch_schema_from_transport=False,
    ):
        assert not (
            type_def and introspection
        ), "Cant provide introspection type definition at the same time"
        if transport and fetch_schema_from_transport:
            assert (
                not schema
            ), "Cant fetch the schema from transport if is already provided"
            if not isinstance(transport, AsyncTransport):
                # For sync transports, we fetch the schema directly
                introspection = transport.execute(parse(introspection_query)).data
        if introspection:
            assert not schema, "Cant provide introspection and schema at the same time"
            schema = build_client_schema(introspection)
        elif type_def:
            assert (
                not schema
            ), "Cant provide Type definition and schema at the same time"
            type_def_ast = parse(type_def)
            schema = build_ast_schema(type_def_ast)
        elif schema and not transport:
            transport = LocalSchemaTransport(schema)

        self.schema = schema
        self.introspection = introspection
        self.transport = transport
        self.fetch_schema_from_transport = fetch_schema_from_transport

    async def execute_async(self, document: Document, *args, **kwargs) -> Dict:
        async with self as session:
            return await session.execute(document, *args, **kwargs)

    def execute(self, document: Document, *args, **kwargs) -> Dict:
        """Execute the provided document AST against the configured remote server.

        This function WILL BLOCK until the result is received from the server.

        Either the transport is sync and we execute the query synchronously directly
        OR the transport is async and we execute the query in the asyncio loop (blocking here until answer)
        """

        if isinstance(self.transport, AsyncTransport):

            loop = asyncio.get_event_loop()

            timeout = kwargs.get("timeout", 10)
            data: Dict[Any, Any] = loop.run_until_complete(
                asyncio.wait_for(self.execute_async(document, *args, **kwargs), timeout)
            )

            return data

        else:  # Sync transports

            if self.schema:
                self.validate(document)

            result: ExecutionResult = self.transport.execute(document, *args, **kwargs)

            if result.errors:
                raise TransportQueryError(str(result.errors[0]))

            # Running cast to make mypy happy. result.data should never be None here
            return cast(Dict[Any, Any], result.data)

    async def subscribe_async(
        self, document: Document, *args, **kwargs
    ) -> AsyncGenerator[Dict, None]:
        async with self as session:
            async for result in session.subscribe(document, *args, **kwargs):
                yield result

    def subscribe(
        self, document: Document, *args, **kwargs
    ) -> Generator[Dict, None, None]:
        """Execute a GraphQL subscription with a python generator.

        We need an async transport for this functionality.
        """

        async_generator = self.subscribe_async(document, *args, **kwargs)

        loop = asyncio.get_event_loop()

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

    async def __aexit__(self, *args):

        await self.transport.close()

    def close(self):
        """Close the client and it's underlying transport (only for Sync transports)"""
        if not isinstance(self.transport, AsyncTransport):
            self.transport.close()

    def __enter__(self):
        assert not isinstance(
            self.transport, AsyncTransport
        ), "Only a sync transport can be use. Use 'async with Client(...)' instead"
        return self

    def __exit__(self, *args):
        self.close()


class AsyncClientSession:
    """ An instance of this class is created when using 'async with' on the client.

    It contains the async methods (execute, subscribe) to send queries with the async transports"""

    def __init__(self, client: AsyncClient):
        self.client = client

    async def validate(self, document: Document):
        """ Fetch schema from transport if needed and validate document if schema is present """

        # Get schema from transport if needed
        if self.client.fetch_schema_from_transport and not self.client.schema:
            await self.fetch_schema()

        # Validate document
        if self.client.schema:
            self.client.validate(document)

    async def subscribe(
        self, document: Document, *args, **kwargs
    ) -> AsyncGenerator[Dict, None]:

        # Fetch schema from transport if needed and validate document if schema is present
        await self.validate(document)

        # Subscribe to the transport and yield data or raise error
        async for result in self.transport.subscribe(document, *args, **kwargs):
            if result.errors:
                raise TransportQueryError(str(result.errors[0]))

            yield result.data

    async def execute(self, document: Document, *args, **kwargs) -> Dict:

        # Fetch schema from transport if needed and validate document if schema is present
        await self.validate(document)

        # Execute the query with the transport
        result = await self.transport.execute(document, *args, **kwargs)

        # Raise an error if an error is returned in the ExecutionResult object
        if result.errors:
            raise TransportQueryError(str(result.errors[0]))

        return result.data

    async def fetch_schema(self) -> None:
        execution_result = await self.transport.execute(parse(introspection_query))
        self.client.introspection = execution_result.data
        self.client.schema = build_client_schema(self.client.introspection)

    @property
    def transport(self):
        return self.client.transport
