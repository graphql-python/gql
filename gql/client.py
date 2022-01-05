import asyncio
import sys
import warnings
from typing import Any, AsyncGenerator, Dict, Generator, Optional, Union, overload

from graphql import (
    DocumentNode,
    ExecutionResult,
    GraphQLSchema,
    build_ast_schema,
    get_introspection_query,
    parse,
    validate,
)

from .transport.async_transport import AsyncTransport
from .transport.exceptions import TransportQueryError
from .transport.local_schema import LocalSchemaTransport
from .transport.transport import Transport
from .utilities import build_client_schema
from .utilities import parse_result as parse_result_fn
from .utilities import serialize_variable_values

"""
Load the appropriate instance of the Literal type
Note: we cannot use try: except ImportError because of the following mypy issue:
https://github.com/python/mypy/issues/8520
"""
if sys.version_info[:2] >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal  # pragma: no cover


class Client:
    """The Client class is the main entrypoint to execute GraphQL requests
    on a GQL transport.

    It can take sync or async transports as argument and can either execute
    and subscribe to requests itself with the
    :func:`execute <gql.client.Client.execute>` and
    :func:`subscribe <gql.client.Client.subscribe>` methods
    OR can be used to get a sync or async session depending on the
    transport type.

    To connect to an :ref:`async transport <async_transports>` and get an
    :class:`async session <gql.client.AsyncClientSession>`,
    use :code:`async with client as session:`

    To connect to a :ref:`sync transport <sync_transports>` and get a
    :class:`sync session <gql.client.SyncClientSession>`,
    use :code:`with client as session:`
    """

    def __init__(
        self,
        schema: Optional[Union[str, GraphQLSchema]] = None,
        introspection=None,
        transport: Optional[Union[Transport, AsyncTransport]] = None,
        fetch_schema_from_transport: bool = False,
        execute_timeout: Optional[Union[int, float]] = 10,
        serialize_variables: bool = False,
        parse_results: bool = False,
    ):
        """Initialize the client with the given parameters.

        :param schema: an optional GraphQL Schema for local validation
                See :ref:`schema_validation`
        :param transport: The provided :ref:`transport <Transports>`.
        :param fetch_schema_from_transport: Boolean to indicate that if we want to fetch
                the schema from the transport using an introspection query
        :param execute_timeout: The maximum time in seconds for the execution of a
                request before a TimeoutError is raised. Only used for async transports.
                Passing None results in waiting forever for a response.
        :param serialize_variables: whether the variable values should be
            serialized. Used for custom scalars and/or enums. Default: False.
        :param parse_results: Whether gql will try to parse the serialized output
                sent by the backend. Can be used to unserialize custom scalars or enums.
        """

        if introspection:
            assert (
                not schema
            ), "Cannot provide introspection and schema at the same time."
            schema = build_client_schema(introspection)

        if isinstance(schema, str):
            type_def_ast = parse(schema)
            schema = build_ast_schema(type_def_ast)

        if transport and fetch_schema_from_transport:
            assert (
                not schema
            ), "Cannot fetch the schema from transport if is already provided."

            assert not type(transport).__name__ == "AppSyncWebsocketsTransport", (
                "fetch_schema_from_transport=True is not allowed "
                "for AppSyncWebsocketsTransport "
                "because only subscriptions are allowed on the realtime endpoint."
            )

        if schema and not transport:
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

        # Enforced timeout of the execute function (only for async transports)
        self.execute_timeout = execute_timeout

        self.serialize_variables = serialize_variables
        self.parse_results = parse_results

    def validate(self, document: DocumentNode):
        """:meta private:"""
        assert (
            self.schema
        ), "Cannot validate the document locally, you need to pass a schema."

        validation_errors = validate(self.schema, document)
        if validation_errors:
            raise validation_errors[0]

    def execute_sync(self, document: DocumentNode, *args, **kwargs) -> Dict:
        """:meta private:"""
        with self as session:
            return session.execute(document, *args, **kwargs)

    async def execute_async(self, document: DocumentNode, *args, **kwargs) -> Dict:
        """:meta private:"""
        async with self as session:
            return await session.execute(document, *args, **kwargs)

    def execute(self, document: DocumentNode, *args, **kwargs) -> Dict:
        """Execute the provided document AST against the remote server using
        the transport provided during init.

        This function **WILL BLOCK** until the result is received from the server.

        Either the transport is sync and we execute the query synchronously directly
        OR the transport is async and we execute the query in the asyncio loop
        (blocking here until answer).

        This method will:

         - connect using the transport to get a session
         - execute the GraphQL request on the transport session
         - close the session and close the connection to the server

         If you have multiple requests to send, it is better to get your own session
         and execute the requests in your session.

         The extra arguments passed in the method will be passed to the transport
         execute method.
        """

        if isinstance(self.transport, AsyncTransport):

            # Get the current asyncio event loop
            # Or create a new event loop if there isn't one (in a new Thread)
            try:
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore", message="There is no current event loop"
                    )
                    loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            assert not loop.is_running(), (
                "Cannot run client.execute(query) if an asyncio loop is running."
                " Use 'await client.execute_async(query)' instead."
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
        """:meta private:"""
        async with self as session:

            generator: AsyncGenerator[Dict, None] = session.subscribe(
                document, *args, **kwargs
            )

            async for result in generator:
                yield result

    def subscribe(
        self, document: DocumentNode, *args, **kwargs
    ) -> Generator[Dict, None, None]:
        """Execute a GraphQL subscription with a python generator.

        We need an async transport for this functionality.
        """

        # Get the current asyncio event loop
        # Or create a new event loop if there isn't one (in a new Thread)
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", message="There is no current event loop"
                )
                loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async_generator = self.subscribe_async(document, *args, **kwargs)

        assert not loop.is_running(), (
            "Cannot run client.subscribe(query) if an asyncio loop is running."
            " Use 'await client.subscribe_async(query)' instead."
        )

        try:
            while True:
                # Note: we need to create a task here in order to be able to close
                # the async generator properly on python 3.8
                # See https://bugs.python.org/issue38559
                generator_task = asyncio.ensure_future(
                    async_generator.__anext__(), loop=loop
                )
                result = loop.run_until_complete(generator_task)
                yield result

        except StopAsyncIteration:
            pass

        except (KeyboardInterrupt, Exception):

            # Graceful shutdown by cancelling the task and waiting clean shutdown
            generator_task.cancel()

            try:
                loop.run_until_complete(generator_task)
            except (StopAsyncIteration, asyncio.CancelledError):
                pass

            # Then reraise the exception
            raise

    async def __aenter__(self):

        assert isinstance(
            self.transport, AsyncTransport
        ), "Only a transport of type AsyncTransport can be used asynchronously"

        await self.transport.connect()

        if not hasattr(self, "session"):
            self.session = AsyncClientSession(client=self)

        # Get schema from transport if needed
        if self.fetch_schema_from_transport and not self.schema:
            await self.session.fetch_schema()

        return self.session

    async def __aexit__(self, exc_type, exc, tb):

        await self.transport.close()

    def __enter__(self):

        assert not isinstance(self.transport, AsyncTransport), (
            "Only a sync transport can be used."
            " Use 'async with Client(...) as session:' instead"
        )

        self.transport.connect()

        if not hasattr(self, "session"):
            self.session = SyncClientSession(client=self)

        # Get schema from transport if needed
        if self.fetch_schema_from_transport and not self.schema:
            self.session.fetch_schema()

        return self.session

    def __exit__(self, *args):
        self.transport.close()


class SyncClientSession:
    """An instance of this class is created when using :code:`with` on the client.

    It contains the sync method execute to send queries
    on a sync transport using the same session.
    """

    def __init__(self, client: Client):
        """:param client: the :class:`client <gql.client.Client>` used"""
        self.client = client

    def _execute(
        self,
        document: DocumentNode,
        *args,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        serialize_variables: Optional[bool] = None,
        parse_result: Optional[bool] = None,
        **kwargs,
    ) -> ExecutionResult:
        """Execute the provided document AST synchronously using
        the sync transport, returning an ExecutionResult object.

        :param document: GraphQL query as AST Node object.
        :param variable_values: Dictionary of input parameters.
        :param operation_name: Name of the operation that shall be executed.
        :param serialize_variables: whether the variable values should be
            serialized. Used for custom scalars and/or enums.
            By default use the serialize_variables argument of the client.
        :param parse_result: Whether gql will unserialize the result.
            By default use the parse_results argument of the client.

        The extra arguments are passed to the transport execute method."""

        # Validate document
        if self.client.schema:
            self.client.validate(document)

            # Parse variable values for custom scalars if requested
            if variable_values is not None:
                if serialize_variables or (
                    serialize_variables is None and self.client.serialize_variables
                ):
                    variable_values = serialize_variable_values(
                        self.client.schema,
                        document,
                        variable_values,
                        operation_name=operation_name,
                    )

        result = self.transport.execute(
            document,
            *args,
            variable_values=variable_values,
            operation_name=operation_name,
            **kwargs,
        )

        # Unserialize the result if requested
        if self.client.schema:
            if parse_result or (parse_result is None and self.client.parse_results):
                result.data = parse_result_fn(
                    self.client.schema,
                    document,
                    result.data,
                    operation_name=operation_name,
                )

        return result

    @overload
    def execute(
        self,
        document: DocumentNode,
        *args,
        variable_values: Optional[Dict[str, Any]] = ...,
        operation_name: Optional[str] = ...,
        serialize_variables: Optional[bool] = ...,
        parse_result: Optional[bool] = ...,
        get_execution_result: Literal[False] = ...,
        **kwargs,
    ) -> Dict[str, Any]:
        ...  # pragma: no cover

    @overload
    def execute(
        self,
        document: DocumentNode,
        *args,
        variable_values: Optional[Dict[str, Any]] = ...,
        operation_name: Optional[str] = ...,
        serialize_variables: Optional[bool] = ...,
        parse_result: Optional[bool] = ...,
        get_execution_result: Literal[True],
        **kwargs,
    ) -> ExecutionResult:
        ...  # pragma: no cover

    def execute(
        self,
        document: DocumentNode,
        *args,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        serialize_variables: Optional[bool] = None,
        parse_result: Optional[bool] = None,
        get_execution_result: bool = False,
        **kwargs,
    ) -> Union[Dict[str, Any], ExecutionResult]:
        """Execute the provided document AST synchronously using
        the sync transport.

        Raises a TransportQueryError if an error has been returned in
            the ExecutionResult.

        :param document: GraphQL query as AST Node object.
        :param variable_values: Dictionary of input parameters.
        :param operation_name: Name of the operation that shall be executed.
        :param serialize_variables: whether the variable values should be
            serialized. Used for custom scalars and/or enums.
            By default use the serialize_variables argument of the client.
        :param parse_result: Whether gql will unserialize the result.
            By default use the parse_results argument of the client.
        :param get_execution_result: return the full ExecutionResult instance instead of
            only the "data" field. Necessary if you want to get the "extensions" field.

        The extra arguments are passed to the transport execute method."""

        # Validate and execute on the transport
        result = self._execute(
            document,
            *args,
            variable_values=variable_values,
            operation_name=operation_name,
            serialize_variables=serialize_variables,
            parse_result=parse_result,
            **kwargs,
        )

        # Raise an error if an error is returned in the ExecutionResult object
        if result.errors:
            raise TransportQueryError(
                str(result.errors[0]),
                errors=result.errors,
                data=result.data,
                extensions=result.extensions,
            )

        assert (
            result.data is not None
        ), "Transport returned an ExecutionResult without data or errors"

        if get_execution_result:
            return result

        return result.data

    def fetch_schema(self) -> None:
        """Fetch the GraphQL schema explicitely using introspection.

        Don't use this function and instead set the fetch_schema_from_transport
        attribute to True"""
        execution_result = self.transport.execute(parse(get_introspection_query()))
        self.client.introspection = execution_result.data
        self.client.schema = build_client_schema(self.client.introspection)

    @property
    def transport(self):
        return self.client.transport


class AsyncClientSession:
    """An instance of this class is created when using :code:`async with` on a
    :class:`client <gql.client.Client>`.

    It contains the async methods (execute, subscribe) to send queries
    on an async transport using the same session.
    """

    def __init__(self, client: Client):
        """:param client: the :class:`client <gql.client.Client>` used"""
        self.client = client

    async def _subscribe(
        self,
        document: DocumentNode,
        *args,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        serialize_variables: Optional[bool] = None,
        parse_result: Optional[bool] = None,
        **kwargs,
    ) -> AsyncGenerator[ExecutionResult, None]:
        """Coroutine to subscribe asynchronously to the provided document AST
        asynchronously using the async transport,
        returning an async generator producing ExecutionResult objects.

        * Validate the query with the schema if provided.
        * Serialize the variable_values if requested.

        :param document: GraphQL query as AST Node object.
        :param variable_values: Dictionary of input parameters.
        :param operation_name: Name of the operation that shall be executed.
        :param serialize_variables: whether the variable values should be
            serialized. Used for custom scalars and/or enums.
            By default use the serialize_variables argument of the client.
        :param parse_result: Whether gql will unserialize the result.
            By default use the parse_results argument of the client.

        The extra arguments are passed to the transport subscribe method."""

        # Validate document
        if self.client.schema:
            self.client.validate(document)

            # Parse variable values for custom scalars if requested
            if variable_values is not None:
                if serialize_variables or (
                    serialize_variables is None and self.client.serialize_variables
                ):
                    variable_values = serialize_variable_values(
                        self.client.schema,
                        document,
                        variable_values,
                        operation_name=operation_name,
                    )

        # Subscribe to the transport
        inner_generator: AsyncGenerator[
            ExecutionResult, None
        ] = self.transport.subscribe(
            document,
            *args,
            variable_values=variable_values,
            operation_name=operation_name,
            **kwargs,
        )

        # Keep a reference to the inner generator to allow the user to call aclose()
        # before a break if python version is too old (pypy3 py 3.6.1)
        self._generator = inner_generator

        try:
            async for result in inner_generator:

                if self.client.schema:
                    if parse_result or (
                        parse_result is None and self.client.parse_results
                    ):
                        result.data = parse_result_fn(
                            self.client.schema,
                            document,
                            result.data,
                            operation_name=operation_name,
                        )

                yield result

        finally:
            await inner_generator.aclose()

    @overload
    def subscribe(
        self,
        document: DocumentNode,
        *args,
        variable_values: Optional[Dict[str, Any]] = ...,
        operation_name: Optional[str] = ...,
        serialize_variables: Optional[bool] = ...,
        parse_result: Optional[bool] = ...,
        get_execution_result: Literal[False] = ...,
        **kwargs,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        ...  # pragma: no cover

    @overload
    def subscribe(
        self,
        document: DocumentNode,
        *args,
        variable_values: Optional[Dict[str, Any]] = ...,
        operation_name: Optional[str] = ...,
        serialize_variables: Optional[bool] = ...,
        parse_result: Optional[bool] = ...,
        get_execution_result: Literal[True],
        **kwargs,
    ) -> AsyncGenerator[ExecutionResult, None]:
        ...  # pragma: no cover

    async def subscribe(
        self,
        document: DocumentNode,
        *args,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        serialize_variables: Optional[bool] = None,
        parse_result: Optional[bool] = None,
        get_execution_result: bool = False,
        **kwargs,
    ) -> Union[
        AsyncGenerator[Dict[str, Any], None], AsyncGenerator[ExecutionResult, None]
    ]:
        """Coroutine to subscribe asynchronously to the provided document AST
        asynchronously using the async transport.

        Raises a TransportQueryError if an error has been returned in
            the ExecutionResult.

        :param document: GraphQL query as AST Node object.
        :param variable_values: Dictionary of input parameters.
        :param operation_name: Name of the operation that shall be executed.
        :param serialize_variables: whether the variable values should be
            serialized. Used for custom scalars and/or enums.
            By default use the serialize_variables argument of the client.
        :param parse_result: Whether gql will unserialize the result.
            By default use the parse_results argument of the client.
        :param get_execution_result: yield the full ExecutionResult instance instead of
            only the "data" field. Necessary if you want to get the "extensions" field.

        The extra arguments are passed to the transport subscribe method."""

        inner_generator: AsyncGenerator[ExecutionResult, None] = self._subscribe(
            document,
            *args,
            variable_values=variable_values,
            operation_name=operation_name,
            serialize_variables=serialize_variables,
            parse_result=parse_result,
            **kwargs,
        )

        try:
            # Validate and subscribe on the transport
            async for result in inner_generator:

                # Raise an error if an error is returned in the ExecutionResult object
                if result.errors:
                    raise TransportQueryError(
                        str(result.errors[0]),
                        errors=result.errors,
                        data=result.data,
                        extensions=result.extensions,
                    )

                elif result.data is not None:
                    if get_execution_result:
                        yield result
                    else:
                        yield result.data
        finally:
            await inner_generator.aclose()

    async def _execute(
        self,
        document: DocumentNode,
        *args,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        serialize_variables: Optional[bool] = None,
        parse_result: Optional[bool] = None,
        **kwargs,
    ) -> ExecutionResult:
        """Coroutine to execute the provided document AST asynchronously using
        the async transport, returning an ExecutionResult object.

        * Validate the query with the schema if provided.
        * Serialize the variable_values if requested.

        :param document: GraphQL query as AST Node object.
        :param variable_values: Dictionary of input parameters.
        :param operation_name: Name of the operation that shall be executed.
        :param serialize_variables: whether the variable values should be
            serialized. Used for custom scalars and/or enums.
            By default use the serialize_variables argument of the client.
        :param parse_result: Whether gql will unserialize the result.
            By default use the parse_results argument of the client.

        The extra arguments are passed to the transport execute method."""

        # Validate document
        if self.client.schema:
            self.client.validate(document)

            # Parse variable values for custom scalars if requested
            if variable_values is not None:
                if serialize_variables or (
                    serialize_variables is None and self.client.serialize_variables
                ):
                    variable_values = serialize_variable_values(
                        self.client.schema,
                        document,
                        variable_values,
                        operation_name=operation_name,
                    )

        # Execute the query with the transport with a timeout
        result = await asyncio.wait_for(
            self.transport.execute(
                document,
                variable_values=variable_values,
                operation_name=operation_name,
                *args,
                **kwargs,
            ),
            self.client.execute_timeout,
        )

        # Unserialize the result if requested
        if self.client.schema:
            if parse_result or (parse_result is None and self.client.parse_results):
                result.data = parse_result_fn(
                    self.client.schema,
                    document,
                    result.data,
                    operation_name=operation_name,
                )

        return result

    @overload
    async def execute(
        self,
        document: DocumentNode,
        *args,
        variable_values: Optional[Dict[str, Any]] = ...,
        operation_name: Optional[str] = ...,
        serialize_variables: Optional[bool] = ...,
        parse_result: Optional[bool] = ...,
        get_execution_result: Literal[False] = ...,
        **kwargs,
    ) -> Dict[str, Any]:
        ...  # pragma: no cover

    @overload
    async def execute(
        self,
        document: DocumentNode,
        *args,
        variable_values: Optional[Dict[str, Any]] = ...,
        operation_name: Optional[str] = ...,
        serialize_variables: Optional[bool] = ...,
        parse_result: Optional[bool] = ...,
        get_execution_result: Literal[True],
        **kwargs,
    ) -> ExecutionResult:
        ...  # pragma: no cover

    async def execute(
        self,
        document: DocumentNode,
        *args,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        serialize_variables: Optional[bool] = None,
        parse_result: Optional[bool] = None,
        get_execution_result: bool = False,
        **kwargs,
    ) -> Union[Dict[str, Any], ExecutionResult]:
        """Coroutine to execute the provided document AST asynchronously using
        the async transport.

        Raises a TransportQueryError if an error has been returned in
            the ExecutionResult.

        :param document: GraphQL query as AST Node object.
        :param variable_values: Dictionary of input parameters.
        :param operation_name: Name of the operation that shall be executed.
        :param serialize_variables: whether the variable values should be
            serialized. Used for custom scalars and/or enums.
            By default use the serialize_variables argument of the client.
        :param parse_result: Whether gql will unserialize the result.
            By default use the parse_results argument of the client.
        :param get_execution_result: return the full ExecutionResult instance instead of
            only the "data" field. Necessary if you want to get the "extensions" field.

        The extra arguments are passed to the transport execute method."""

        # Validate and execute on the transport
        result = await self._execute(
            document,
            *args,
            variable_values=variable_values,
            operation_name=operation_name,
            serialize_variables=serialize_variables,
            parse_result=parse_result,
            **kwargs,
        )

        # Raise an error if an error is returned in the ExecutionResult object
        if result.errors:
            raise TransportQueryError(
                str(result.errors[0]),
                errors=result.errors,
                data=result.data,
                extensions=result.extensions,
            )

        assert (
            result.data is not None
        ), "Transport returned an ExecutionResult without data or errors"

        if get_execution_result:
            return result

        return result.data

    async def fetch_schema(self) -> None:
        """Fetch the GraphQL schema explicitely using introspection.

        Don't use this function and instead set the fetch_schema_from_transport
        attribute to True"""
        execution_result = await self.transport.execute(
            parse(get_introspection_query())
        )
        self.client.introspection = execution_result.data
        self.client.schema = build_client_schema(self.client.introspection)

    @property
    def transport(self):
        return self.client.transport
