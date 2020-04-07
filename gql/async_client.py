from graphql import build_ast_schema, build_client_schema, introspection_query, parse
from graphql.execution import ExecutionResult
from graphql.language.ast import Document

from typing import AsyncGenerator

from gql.transport import AsyncTransport
from gql import Client


class AsyncClient(Client):
    def __init__(
        self, schema=None, introspection=None, type_def=None, transport=None,
    ):
        assert isinstance(
            transport, AsyncTransport
        ), "Only a transport of type AsyncTransport is supported on AsyncClient"
        assert not (
            type_def and introspection
        ), "Cant provide introspection type definition at the same time"
        if introspection:
            assert not schema, "Cant provide introspection and schema at the same time"
            schema = build_client_schema(introspection)
        elif type_def:
            assert (
                not schema
            ), "Cant provide Type definition and schema at the same time"
            type_def_ast = parse(type_def)
            schema = build_ast_schema(type_def_ast)

        self.schema = schema
        self.introspection = introspection
        self.transport = transport

    async def subscribe(
        self, document: Document, *args, **kwargs
    ) -> AsyncGenerator[ExecutionResult, None]:
        if self.schema:
            self.validate(document)

        async for result in self.transport.subscribe(document, *args, **kwargs):
            yield result

    async def execute(self, document: Document, *args, **kwargs) -> ExecutionResult:
        if self.schema:
            self.validate(document)

        return await self.transport.execute(document, *args, **kwargs)

    async def fetch_schema(self) -> None:
        execution_result = await self.transport.execute(parse(introspection_query))
        self.introspection = execution_result.data
        self.schema = build_client_schema(self.introspection)

    async def __aenter__(self):
        await self.transport.connect()
        return self

    async def __aexit__(self, *args):
        await self.transport.close()
