import asyncio
import io
import json
import logging
from ssl import SSLContext
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)

import aiohttp
from aiohttp.client_exceptions import ClientResponseError
from aiohttp.client_reqrep import Fingerprint
from aiohttp.helpers import BasicAuth
from aiohttp.typedefs import LooseCookies, LooseHeaders
from graphql import ExecutionResult
from multidict import CIMultiDictProxy

from ..graphql_request import GraphQLRequest
from .appsync_auth import AppSyncAuthentication
from .async_transport import AsyncTransport
from .common.aiohttp_closed_event import create_aiohttp_closed_event
from .common.batch import get_batch_execution_result_list
from .exceptions import (
    TransportAlreadyConnected,
    TransportClosed,
    TransportConnectionFailed,
    TransportError,
    TransportProtocolError,
    TransportServerError,
)
from .file_upload import FileVar, close_files, extract_files, open_files

log = logging.getLogger(__name__)


class AIOHTTPTransport(AsyncTransport):
    """:ref:`Async Transport <async_transports>` to execute GraphQL queries
    on remote servers with an HTTP connection.

    This transport use the aiohttp library with asyncio.
    """

    file_classes: Tuple[Type[Any], ...] = (
        io.IOBase,
        aiohttp.StreamReader,
        AsyncGenerator,
    )

    def __init__(
        self,
        url: str,
        headers: Optional[LooseHeaders] = None,
        cookies: Optional[LooseCookies] = None,
        auth: Optional[Union[BasicAuth, "AppSyncAuthentication"]] = None,
        ssl: Union[SSLContext, bool, Fingerprint] = True,
        timeout: Optional[int] = None,
        ssl_close_timeout: Optional[Union[int, float]] = 10,
        json_serialize: Callable = json.dumps,
        json_deserialize: Callable = json.loads,
        client_session_args: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize the transport with the given aiohttp parameters.

        :param url: The GraphQL server URL. Example: 'https://server.com:PORT/path'.
        :param headers: Dict of HTTP Headers.
        :param cookies: Dict of HTTP cookies.
        :param auth: BasicAuth object to enable Basic HTTP auth if needed
                     Or Appsync Authentication class
        :param ssl: ssl_context of the connection.
                    Use ssl=False to not verify ssl certificates.
        :param ssl_close_timeout: Timeout in seconds to wait for the ssl connection
                                  to close properly
        :param json_serialize: Json serializer callable.
                By default json.dumps() function
        :param json_deserialize: Json deserializer callable.
                By default json.loads() function
        :param client_session_args: Dict of extra args passed to
                `aiohttp.ClientSession`_

        .. _aiohttp.ClientSession:
          https://docs.aiohttp.org/en/stable/client_reference.html#aiohttp.ClientSession
        """
        self.url: str = url
        self.headers: Optional[LooseHeaders] = headers
        self.cookies: Optional[LooseCookies] = cookies
        self.auth: Optional[Union[BasicAuth, "AppSyncAuthentication"]] = auth
        self.ssl: Union[SSLContext, bool, Fingerprint] = ssl
        self.timeout: Optional[int] = timeout
        self.ssl_close_timeout: Optional[Union[int, float]] = ssl_close_timeout
        self.client_session_args = client_session_args
        self.session: Optional[aiohttp.ClientSession] = None
        self.response_headers: Optional[CIMultiDictProxy[str]]
        self.json_serialize: Callable = json_serialize
        self.json_deserialize: Callable = json_deserialize

    async def connect(self) -> None:
        """Coroutine which will create an aiohttp ClientSession() as self.session.

        Don't call this coroutine directly on the transport, instead use
        :code:`async with` on the client and this coroutine will be executed
        to create the session.

        Should be cleaned with a call to the close coroutine.
        """

        if self.session is None:

            client_session_args: Dict[str, Any] = {
                "cookies": self.cookies,
                "headers": self.headers,
                "auth": (
                    None if isinstance(self.auth, AppSyncAuthentication) else self.auth
                ),
                "json_serialize": self.json_serialize,
            }

            if self.timeout is not None:
                client_session_args["timeout"] = aiohttp.ClientTimeout(
                    total=self.timeout
                )

            # Adding custom parameters passed from init
            if self.client_session_args:
                client_session_args.update(self.client_session_args)

            log.debug("Connecting transport")

            self.session = aiohttp.ClientSession(**client_session_args)

        else:
            raise TransportAlreadyConnected("Transport is already connected")

    async def close(self) -> None:
        """Coroutine which will close the aiohttp session.

        Don't call this coroutine directly on the transport, instead use
        :code:`async with` on the client and this coroutine will be executed
        when you exit the async context manager.
        """
        if self.session is not None:

            log.debug("Closing transport")

            if (
                self.client_session_args
                and self.client_session_args.get("connector_owner") is False
            ):

                log.debug("connector_owner is False -> not closing connector")

            else:
                closed_event = create_aiohttp_closed_event(self.session)
                await self.session.close()
                try:
                    await asyncio.wait_for(closed_event.wait(), self.ssl_close_timeout)
                except asyncio.TimeoutError:
                    pass

        self.session = None

    def _prepare_request(
        self,
        request: Union[GraphQLRequest, List[GraphQLRequest]],
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

        # Pass post_args to aiohttp post method
        if extra_args:
            post_args.update(extra_args)

        # Add headers for AppSync if requested
        if isinstance(self.auth, AppSyncAuthentication):
            post_args["headers"] = self.auth.get_headers(
                self.json_serialize(payload),
                {"content-type": "application/json"},
            )

        return post_args

    def _prepare_file_uploads(
        self, request: GraphQLRequest, payload: Dict[str, Any]
    ) -> Dict[str, Any]:

        # If the upload_files flag is set, then we need variable_values
        variable_values = request.variable_values
        assert variable_values is not None

        # If we upload files, we will extract the files present in the
        # variable_values dict and replace them by null values
        nulled_variable_values, files = extract_files(
            variables=variable_values,
            file_classes=self.file_classes,
        )

        # Opening the files using the FileVar parameters
        open_files(list(files.values()), transport_supports_streaming=True)
        self.files = files

        # Save the nulled variable values in the payload
        payload["variables"] = nulled_variable_values

        # Prepare aiohttp to send multipart-encoded data
        data = aiohttp.FormData()

        # Generate the file map
        # path is nested in a list because the spec allows multiple pointers
        # to the same file. But we don't support that.
        # Will generate something like {"0": ["variables.file"]}
        file_map = {str(i): [path] for i, path in enumerate(files)}

        # Enumerate the file streams
        # Will generate something like {'0': FileVar object}
        file_vars = {str(i): files[path] for i, path in enumerate(files)}

        # Add the payload to the operations field
        operations_str = self.json_serialize(payload)
        log.debug("operations %s", operations_str)
        data.add_field("operations", operations_str, content_type="application/json")

        # Add the file map field
        file_map_str = self.json_serialize(file_map)
        log.debug("file_map %s", file_map_str)
        data.add_field("map", file_map_str, content_type="application/json")

        for k, file_var in file_vars.items():
            assert isinstance(file_var, FileVar)

            data.add_field(
                k,
                file_var.f,
                filename=file_var.filename,
                content_type=file_var.content_type,
            )

        post_args: Dict[str, Any] = {"data": data}

        return post_args

    @staticmethod
    def _raise_transport_server_error_if_status_more_than_400(
        resp: aiohttp.ClientResponse,
    ) -> None:
        # If the status is >400,
        # then we need to raise a TransportServerError
        try:
            # Raise ClientResponseError if response status is 400 or higher
            resp.raise_for_status()
        except ClientResponseError as e:
            raise TransportServerError(str(e), e.status) from e

    @classmethod
    async def _raise_response_error(
        cls,
        resp: aiohttp.ClientResponse,
        reason: str,
    ) -> None:
        # We raise a TransportServerError if status code is 400 or higher
        # We raise a TransportProtocolError in the other cases

        cls._raise_transport_server_error_if_status_more_than_400(resp)

        result_text = await resp.text()
        raise TransportProtocolError(
            f"Server did not return a valid GraphQL result: "
            f"{reason}: "
            f"{result_text}"
        )

    async def _get_json_result(self, response: aiohttp.ClientResponse) -> Any:

        # Saving latest response headers in the transport
        self.response_headers = response.headers

        try:
            result = await response.json(loads=self.json_deserialize, content_type=None)

            if log.isEnabledFor(logging.DEBUG):
                result_text = await response.text()
                log.debug("<<< %s", result_text)

        except Exception:
            await self._raise_response_error(response, "Not a JSON answer")

        if result is None:
            await self._raise_response_error(response, "Not a JSON answer")

        return result

    async def _prepare_result(
        self, response: aiohttp.ClientResponse
    ) -> ExecutionResult:

        result = await self._get_json_result(response)

        if "errors" not in result and "data" not in result:
            await self._raise_response_error(
                response, 'No "data" or "errors" keys in answer'
            )

        return ExecutionResult(
            errors=result.get("errors"),
            data=result.get("data"),
            extensions=result.get("extensions"),
        )

    async def _prepare_batch_result(
        self,
        reqs: List[GraphQLRequest],
        response: aiohttp.ClientResponse,
    ) -> List[ExecutionResult]:

        answers = await self._get_json_result(response)

        try:
            return get_batch_execution_result_list(reqs, answers)
        except TransportProtocolError:
            # Raise a TransportServerError if status > 400
            self._raise_transport_server_error_if_status_more_than_400(response)
            # In other cases, raise a TransportProtocolError
            raise

    async def execute(
        self,
        request: GraphQLRequest,
        *,
        extra_args: Optional[Dict[str, Any]] = None,
        upload_files: bool = False,
    ) -> ExecutionResult:
        """Execute the provided request against the configured remote server
        using the current session.
        This uses the aiohttp library to perform a HTTP POST request asynchronously
        to the remote server.

        Don't call this coroutine directly on the transport, instead use
        :code:`execute` on a client or a session.

        :param request: GraphQL request as a
                        :class:`GraphQLRequest <gql.GraphQLRequest>` object.
        :param extra_args: additional arguments to send to the aiohttp post method
        :param upload_files: Set to True if you want to put files in the variable values
        :returns: an ExecutionResult object.
        """

        if self.session is None:
            raise TransportClosed("Transport is not connected")

        post_args = self._prepare_request(
            request,
            extra_args,
            upload_files,
        )

        try:
            async with self.session.post(self.url, ssl=self.ssl, **post_args) as resp:
                return await self._prepare_result(resp)
        except TransportError:
            raise
        except Exception as e:
            raise TransportConnectionFailed(str(e)) from e
        finally:
            if upload_files:
                close_files(list(self.files.values()))

    async def execute_batch(
        self,
        reqs: List[GraphQLRequest],
        extra_args: Optional[Dict[str, Any]] = None,
    ) -> List[ExecutionResult]:
        """Execute multiple GraphQL requests in a batch.

        Don't call this coroutine directly on the transport, instead use
        :code:`execute_batch` on a client or a session.

        :param reqs: GraphQL requests as a list of GraphQLRequest objects.
        :param extra_args: additional arguments to send to the aiohttp post method
        :return: A list of results of execution.
            For every result `data` is the result of executing the query,
            `errors` is null if no errors occurred, and is a non-empty array
            if an error occurred.
        """

        if self.session is None:
            raise TransportClosed("Transport is not connected")

        post_args = self._prepare_request(
            reqs,
            extra_args,
        )

        try:
            async with self.session.post(self.url, ssl=self.ssl, **post_args) as resp:
                return await self._prepare_batch_result(reqs, resp)
        except TransportError:
            raise
        except Exception as e:
            raise TransportConnectionFailed(str(e)) from e

    def subscribe(
        self,
        request: GraphQLRequest,
    ) -> AsyncGenerator[ExecutionResult, None]:
        """Subscribe is not supported on HTTP.

        :meta private:
        """
        raise NotImplementedError(" The HTTP transport does not support subscriptions")
