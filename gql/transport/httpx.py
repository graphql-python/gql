import io
import json
import logging
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    List,
    NoReturn,
    Optional,
    Tuple,
    Type,
    Union,
)

import httpx
from graphql import ExecutionResult

from ..graphql_request import GraphQLRequest
from . import AsyncTransport, Transport
from .common.batch import get_batch_execution_result_list
from .exceptions import (
    TransportAlreadyConnected,
    TransportClosed,
    TransportConnectionFailed,
    TransportProtocolError,
    TransportServerError,
)
from .file_upload import close_files, extract_files, open_files

log = logging.getLogger(__name__)


class _HTTPXTransport:
    file_classes: Tuple[Type[Any], ...] = (io.IOBase,)

    response_headers: Optional[httpx.Headers] = None

    def __init__(
        self,
        url: Union[str, httpx.URL],
        json_serialize: Callable = json.dumps,
        json_deserialize: Callable = json.loads,
        **kwargs: Any,
    ):
        """Initialize the transport with the given httpx parameters.

        :param url: The GraphQL server URL. Example: 'https://server.com:PORT/path'.
        :param json_serialize: Json serializer callable.
                By default json.dumps() function.
        :param json_deserialize: Json deserializer callable.
                By default json.loads() function.
        :param kwargs: Extra args passed to the `httpx` client.
        """
        self.url = url
        self.json_serialize = json_serialize
        self.json_deserialize = json_deserialize
        self.kwargs = kwargs

    def _prepare_request(
        self,
        request: Union[GraphQLRequest, List[GraphQLRequest]],
        *,
        extra_args: Optional[Dict[str, Any]] = None,
        upload_files: bool = False,
    ) -> Dict[str, Any]:

        payload: Dict | List
        if isinstance(request, GraphQLRequest):
            payload = request.payload
        else:
            payload = [req.payload for req in request]

        if upload_files:
            assert isinstance(payload, Dict)
            assert isinstance(request, GraphQLRequest)
            post_args = self._prepare_file_uploads(request, payload)
        else:
            post_args = {"json": payload}

        # Log the payload
        if log.isEnabledFor(logging.DEBUG):
            log.debug(">>> %s", self.json_serialize(payload))

        # Pass post_args to httpx post method
        if extra_args:
            post_args.update(extra_args)

        return post_args

    def _prepare_file_uploads(
        self,
        request: GraphQLRequest,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:

        variable_values = request.variable_values

        # If the upload_files flag is set, then we need variable_values
        assert variable_values is not None

        # If we upload files, we will extract the files present in the
        # variable_values dict and replace them by null values
        nulled_variable_values, files = extract_files(
            variables=variable_values,
            file_classes=self.file_classes,
        )

        # Opening the files using the FileVar parameters
        open_files(list(files.values()))
        self.files = files

        # Save the nulled variable values in the payload
        payload["variables"] = nulled_variable_values

        # Prepare to send multipart-encoded data
        data: Dict[str, Any] = {}
        file_map: Dict[str, List[str]] = {}
        file_streams: Dict[str, Tuple[str, ...]] = {}

        for i, (path, file_var) in enumerate(files.items()):
            key = str(i)

            # Generate the file map
            # path is nested in a list because the spec allows multiple pointers
            # to the same file. But we don't support that.
            # Will generate something like {"0": ["variables.file"]}
            file_map[key] = [path]

            name = key if file_var.filename is None else file_var.filename

            if file_var.content_type is None:
                file_streams[key] = (name, file_var.f)
            else:
                file_streams[key] = (name, file_var.f, file_var.content_type)

        # Add the payload to the operations field
        operations_str = self.json_serialize(payload)
        log.debug("operations %s", operations_str)
        data["operations"] = operations_str

        # Add the file map field
        file_map_str = self.json_serialize(file_map)
        log.debug("file_map %s", file_map_str)
        data["map"] = file_map_str

        return {"data": data, "files": file_streams}

    def _get_json_result(self, response: httpx.Response) -> Any:

        # Saving latest response headers in the transport
        self.response_headers = response.headers

        if log.isEnabledFor(logging.DEBUG):
            log.debug("<<< %s", response.text)

        try:
            result: Dict[str, Any] = self.json_deserialize(response.content)
        except Exception:
            self._raise_response_error(response, "Not a JSON answer")

        return result

    def _prepare_result(self, response: httpx.Response) -> ExecutionResult:

        result = self._get_json_result(response)

        if "errors" not in result and "data" not in result:
            self._raise_response_error(response, 'No "data" or "errors" keys in answer')

        return ExecutionResult(
            errors=result.get("errors"),
            data=result.get("data"),
            extensions=result.get("extensions"),
        )

    def _prepare_batch_result(
        self,
        reqs: List[GraphQLRequest],
        response: httpx.Response,
    ) -> List[ExecutionResult]:

        answers = self._get_json_result(response)

        try:
            return get_batch_execution_result_list(reqs, answers)
        except TransportProtocolError:
            # Raise a TransportServerError if status > 400
            self._raise_transport_server_error_if_status_more_than_400(response)
            # In other cases, raise a TransportProtocolError
            raise

    @staticmethod
    def _raise_transport_server_error_if_status_more_than_400(
        response: httpx.Response,
    ) -> None:
        # If the status is >400,
        # then we need to raise a TransportServerError
        try:
            # Raise a HTTPStatusError if response status is 400 or higher
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise TransportServerError(str(e), e.response.status_code) from e

    @classmethod
    def _raise_response_error(cls, response: httpx.Response, reason: str) -> NoReturn:
        # We raise a TransportServerError if the status code is 400 or higher
        # We raise a TransportProtocolError in the other cases

        cls._raise_transport_server_error_if_status_more_than_400(response)

        raise TransportProtocolError(
            f"Server did not return a GraphQL result: " f"{reason}: " f"{response.text}"
        )


class HTTPXTransport(Transport, _HTTPXTransport):
    """:ref:`Sync Transport <sync_transports>` used to execute GraphQL queries
    on remote servers.

    The transport uses the httpx library to send HTTP POST requests.
    """

    client: Optional[httpx.Client] = None

    def connect(self):
        if self.client:
            raise TransportAlreadyConnected("Transport is already connected")

        log.debug("Connecting transport")

        self.client = httpx.Client(**self.kwargs)

    def execute(
        self,
        request: GraphQLRequest,
        *,
        extra_args: Optional[Dict[str, Any]] = None,
        upload_files: bool = False,
    ) -> ExecutionResult:
        """Execute GraphQL query.

        Execute the provided request against the configured remote server. This
        uses the httpx library to perform a HTTP POST request to the remote server.

        :param request: GraphQL request as a
                        :class:`GraphQLRequest <gql.GraphQLRequest>` object.
        :param extra_args: additional arguments to send to the httpx post method
        :param upload_files: Set to True if you want to put files in the variable values
        :return: The result of execution.
            `data` is the result of executing the query, `errors` is null
            if no errors occurred, and is a non-empty array if an error occurred.
        """
        if not self.client:
            raise TransportClosed("Transport is not connected")

        post_args = self._prepare_request(
            request,
            extra_args=extra_args,
            upload_files=upload_files,
        )

        try:
            response = self.client.post(self.url, **post_args)
        except Exception as e:
            raise TransportConnectionFailed(str(e)) from e
        finally:
            if upload_files:
                close_files(list(self.files.values()))

        return self._prepare_result(response)

    def execute_batch(
        self,
        reqs: List[GraphQLRequest],
        extra_args: Optional[Dict[str, Any]] = None,
    ) -> List[ExecutionResult]:
        """Execute multiple GraphQL requests in a batch.

        Don't call this coroutine directly on the transport, instead use
        :code:`execute_batch` on a client or a session.

        :param reqs: GraphQL requests as a list of GraphQLRequest objects.
        :param extra_args: additional arguments to send to the httpx post method
        :return: A list of results of execution.
            For every result `data` is the result of executing the query,
            `errors` is null if no errors occurred, and is a non-empty array
            if an error occurred.
        """

        if not self.client:
            raise TransportClosed("Transport is not connected")

        post_args = self._prepare_request(
            reqs,
            extra_args=extra_args,
        )

        try:
            response = self.client.post(self.url, **post_args)
        except Exception as e:
            raise TransportConnectionFailed(str(e)) from e

        return self._prepare_batch_result(reqs, response)

    def close(self):
        """Closing the transport by closing the inner session"""
        if self.client:
            self.client.close()
            self.client = None


class HTTPXAsyncTransport(AsyncTransport, _HTTPXTransport):
    """:ref:`Async Transport <async_transports>` used to execute GraphQL queries
    on remote servers.

    The transport uses the httpx library with anyio.
    """

    client: Optional[httpx.AsyncClient] = None

    async def connect(self):
        if self.client:
            raise TransportAlreadyConnected("Transport is already connected")

        log.debug("Connecting transport")

        self.client = httpx.AsyncClient(**self.kwargs)

    async def execute(
        self,
        request: GraphQLRequest,
        *,
        extra_args: Optional[Dict[str, Any]] = None,
        upload_files: bool = False,
    ) -> ExecutionResult:
        """Execute GraphQL query.

        Execute the provided request against the configured remote server. This
        uses the httpx library to perform a HTTP POST request asynchronously to the
        remote server.

        :param request: GraphQL request as a
                        :class:`GraphQLRequest <gql.GraphQLRequest>` object.
        :param extra_args: additional arguments to send to the httpx post method
        :param upload_files: Set to True if you want to put files in the variable values
        :return: The result of execution.
            `data` is the result of executing the query, `errors` is null
            if no errors occurred, and is a non-empty array if an error occurred.
        """
        if not self.client:
            raise TransportClosed("Transport is not connected")

        post_args = self._prepare_request(
            request,
            extra_args=extra_args,
            upload_files=upload_files,
        )

        try:
            response = await self.client.post(self.url, **post_args)
        except Exception as e:
            raise TransportConnectionFailed(str(e)) from e
        finally:
            if upload_files:
                close_files(list(self.files.values()))

        return self._prepare_result(response)

    async def execute_batch(
        self,
        reqs: List[GraphQLRequest],
        extra_args: Optional[Dict[str, Any]] = None,
    ) -> List[ExecutionResult]:
        """Execute multiple GraphQL requests in a batch.

        Don't call this coroutine directly on the transport, instead use
        :code:`execute_batch` on a client or a session.

        :param reqs: GraphQL requests as a list of GraphQLRequest objects.
        :param extra_args: additional arguments to send to the httpx post method
        :return: A list of results of execution.
            For every result `data` is the result of executing the query,
            `errors` is null if no errors occurred, and is a non-empty array
            if an error occurred.
        """

        if not self.client:
            raise TransportClosed("Transport is not connected")

        post_args = self._prepare_request(
            reqs,
            extra_args=extra_args,
        )

        try:
            response = await self.client.post(self.url, **post_args)
        except Exception as e:
            raise TransportConnectionFailed(str(e)) from e

        return self._prepare_batch_result(reqs, response)

    def subscribe(
        self,
        request: GraphQLRequest,
    ) -> AsyncGenerator[ExecutionResult, None]:
        """Subscribe is not supported on HTTP.

        :meta private:
        """
        raise NotImplementedError("The HTTP transport does not support subscriptions")

    async def close(self):
        """Closing the transport by closing the inner session"""
        if self.client:
            await self.client.aclose()
            self.client = None
