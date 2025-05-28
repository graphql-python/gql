import io
import json
import logging
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    List,
    NoReturn,
    Optional,
    Tuple,
    Type,
    Union,
)

import requests
from graphql import ExecutionResult
from requests.adapters import HTTPAdapter, Retry
from requests.auth import AuthBase
from requests.cookies import RequestsCookieJar
from requests.structures import CaseInsensitiveDict
from requests_toolbelt.multipart.encoder import MultipartEncoder

from gql.transport import Transport

from ..graphql_request import GraphQLRequest
from .common.batch import get_batch_execution_result_list
from .exceptions import (
    TransportAlreadyConnected,
    TransportClosed,
    TransportConnectionFailed,
    TransportProtocolError,
    TransportServerError,
)
from .file_upload import FileVar, close_files, extract_files, open_files

log = logging.getLogger(__name__)


class RequestsHTTPTransport(Transport):
    """:ref:`Sync Transport <sync_transports>` used to execute GraphQL queries
    on remote servers.

    The transport uses the requests library to send HTTP POST requests.
    """

    file_classes: Tuple[Type[Any], ...] = (io.IOBase,)
    _default_retry_codes = (429, 500, 502, 503, 504)

    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, Any]] = None,
        cookies: Optional[Union[Dict[str, Any], RequestsCookieJar]] = None,
        auth: Optional[AuthBase] = None,
        use_json: bool = True,
        timeout: Optional[int] = None,
        verify: Union[bool, str] = True,
        retries: int = 0,
        method: str = "POST",
        retry_backoff_factor: float = 0.1,
        retry_status_forcelist: Collection[int] = _default_retry_codes,
        json_serialize: Callable = json.dumps,
        json_deserialize: Callable = json.loads,
        **kwargs: Any,
    ):
        """Initialize the transport with the given request parameters.

        :param url: The GraphQL server URL.
        :param headers: Dictionary of HTTP Headers to send with
            :meth:`requests.Session.request` (Default: None).
        :param cookies: Dict or CookieJar object to send with
            :meth:`requests.Session.request` (Default: None).
        :param auth: Auth tuple or callable to enable Basic/Digest/Custom HTTP Auth
            (Default: None).
        :param use_json: Send request body as JSON instead of form-urlencoded
            (Default: True).
        :param timeout: Specifies a default timeout for requests (Default: None).
        :param verify: Either a boolean, in which case it controls whether we verify
            the server's TLS certificate, or a string, in which case it must be a path
            to a CA bundle to use. (Default: True).
        :param retries: Pre-setup of the requests' Session for performing retries
        :param method: HTTP method used for requests. (Default: POST).
        :param retry_backoff_factor: A backoff factor to apply between attempts after
            the second try. urllib3 will sleep for:
            {backoff factor} * (2 ** ({number of previous retries}))
        :param retry_status_forcelist: A set of integer HTTP status codes that we
            should force a retry on. A retry is initiated if the request method is
            in allowed_methods and the response status code is in status_forcelist.
            (Default: [429, 500, 502, 503, 504])
        :param json_serialize: Json serializer callable.
                By default json.dumps() function
        :param json_deserialize: Json deserializer callable.
                By default json.loads() function
        :param kwargs: Optional arguments that ``request`` takes.
            These can be seen at the `requests`_ source code or the official `docs`_

        .. _requests: https://github.com/psf/requests/blob/master/requests/api.py
        .. _docs: https://requests.readthedocs.io/en/master/
        """
        self.url = url
        self.headers = headers
        self.cookies = cookies
        self.auth = auth
        self.use_json = use_json
        self.default_timeout = timeout
        self.verify = verify
        self.retries = retries
        self.method = method
        self.retry_backoff_factor = retry_backoff_factor
        self.retry_status_forcelist = retry_status_forcelist
        self.json_serialize: Callable = json_serialize
        self.json_deserialize: Callable = json_deserialize
        self.kwargs = kwargs

        self.session: Optional[requests.Session] = None

        self.response_headers: Optional[CaseInsensitiveDict[str]] = None

    def connect(self):
        if self.session is None:
            # Creating a session that can later be re-use to configure custom mechanisms
            self.session = requests.Session()

            # If we specified some retries, we provide a predefined retry-logic
            if self.retries > 0:
                adapter = HTTPAdapter(
                    max_retries=Retry(
                        total=self.retries,
                        backoff_factor=self.retry_backoff_factor,
                        status_forcelist=self.retry_status_forcelist,
                        allowed_methods=None,
                    )
                )
                for prefix in "http://", "https://":
                    self.session.mount(prefix, adapter)
        else:
            raise TransportAlreadyConnected("Transport is already connected")

    def _prepare_request(
        self,
        request: Union[GraphQLRequest, List[GraphQLRequest]],
        *,
        timeout: Optional[int] = None,
        extra_args: Optional[Dict[str, Any]] = None,
        upload_files: bool = False,
    ) -> Dict[str, Any]:

        payload: Dict | List
        if isinstance(request, GraphQLRequest):
            payload = request.payload
        else:
            payload = [req.payload for req in request]

        post_args: Dict[str, Any] = {
            "headers": self.headers,
            "auth": self.auth,
            "cookies": self.cookies,
            "timeout": timeout or self.default_timeout,
            "verify": self.verify,
        }

        if upload_files:
            assert isinstance(payload, Dict)
            assert isinstance(request, GraphQLRequest)
            post_args = self._prepare_file_uploads(
                request=request,
                payload=payload,
                post_args=post_args,
            )

        else:
            data_key = "json" if self.use_json else "data"
            post_args[data_key] = payload

        # Log the payload
        if log.isEnabledFor(logging.DEBUG):
            log.debug(">>> %s", self.json_serialize(payload))

        # Pass kwargs to requests post method
        post_args.update(self.kwargs)

        # Pass post_args to requests post method
        if extra_args:
            post_args.update(extra_args)

        return post_args

    def _prepare_file_uploads(
        self,
        request: GraphQLRequest,
        *,
        payload: Dict[str, Any],
        post_args: Dict[str, Any],
    ) -> Dict[str, Any]:
        # If the upload_files flag is set, then we need variable_values
        assert request.variable_values is not None

        # If we upload files, we will extract the files present in the
        # variable_values dict and replace them by null values
        nulled_variable_values, files = extract_files(
            variables=request.variable_values,
            file_classes=self.file_classes,
        )

        # Opening the files using the FileVar parameters
        open_files(list(files.values()))
        self.files = files

        # Save the nulled variable values in the payload
        payload["variables"] = nulled_variable_values

        # Add the payload to the operations field
        operations_str = self.json_serialize(payload)
        log.debug("operations %s", operations_str)

        # Generate the file map
        # path is nested in a list because the spec allows multiple pointers
        # to the same file. But we don't support that.
        # Will generate something like {"0": ["variables.file"]}
        file_map = {str(i): [path] for i, path in enumerate(files)}

        # Enumerate the file streams
        # Will generate something like {'0': FileVar object}
        file_vars = {str(i): files[path] for i, path in enumerate(files)}

        # Add the file map field
        file_map_str = self.json_serialize(file_map)
        log.debug("file_map %s", file_map_str)

        fields = {"operations": operations_str, "map": file_map_str}

        # Add the extracted files as remaining fields
        for k, file_var in file_vars.items():
            assert isinstance(file_var, FileVar)
            name = k if file_var.filename is None else file_var.filename

            if file_var.content_type is None:
                fields[k] = (name, file_var.f)
            else:
                fields[k] = (name, file_var.f, file_var.content_type)

        # Prepare requests http to send multipart-encoded data
        data = MultipartEncoder(fields=fields)

        post_args["data"] = data

        if post_args["headers"] is None:
            post_args["headers"] = {}
        else:
            post_args["headers"] = dict(post_args["headers"])

        post_args["headers"]["Content-Type"] = data.content_type

        return post_args

    def execute(
        self,
        request: GraphQLRequest,
        timeout: Optional[int] = None,
        extra_args: Optional[Dict[str, Any]] = None,
        upload_files: bool = False,
    ) -> ExecutionResult:
        """Execute GraphQL query.

        Execute the provided request against the configured remote server. This
        uses the requests library to perform a HTTP POST request to the remote server.

        :param request: GraphQL request as a
                        :class:`GraphQLRequest <gql.GraphQLRequest>` object.
        :param timeout: Specifies a default timeout for requests (Default: None).
        :param extra_args: additional arguments to send to the requests post method
        :param upload_files: Set to True if you want to put files in the variable values
        :return: The result of execution.
            `data` is the result of executing the query, `errors` is null
            if no errors occurred, and is a non-empty array if an error occurred.
        """

        if not self.session:
            raise TransportClosed("Transport is not connected")

        post_args = self._prepare_request(
            request,
            timeout=timeout,
            extra_args=extra_args,
            upload_files=upload_files,
        )

        # Using the created session to perform requests
        try:
            response = self.session.request(self.method, self.url, **post_args)
        except Exception as e:
            raise TransportConnectionFailed(str(e)) from e
        finally:
            if upload_files:
                close_files(list(self.files.values()))

        return self._prepare_result(response)

    @staticmethod
    def _raise_transport_server_error_if_status_more_than_400(
        response: requests.Response,
    ) -> None:
        # If the status is >400,
        # then we need to raise a TransportServerError
        try:
            # Raise a HTTPError if response status is 400 or higher
            response.raise_for_status()
        except requests.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else None
            raise TransportServerError(str(e), status_code) from e

    @classmethod
    def _raise_response_error(cls, resp: requests.Response, reason: str) -> NoReturn:
        # We raise a TransportServerError if the status code is 400 or higher
        # We raise a TransportProtocolError in the other cases

        cls._raise_transport_server_error_if_status_more_than_400(resp)

        result_text = resp.text
        raise TransportProtocolError(
            f"Server did not return a GraphQL result: " f"{reason}: " f"{result_text}"
        )

    def execute_batch(
        self,
        reqs: List[GraphQLRequest],
        timeout: Optional[int] = None,
        extra_args: Optional[Dict[str, Any]] = None,
    ) -> List[ExecutionResult]:
        """Execute multiple GraphQL requests in a batch.

        Execute the provided requests against the configured remote server. This
        uses the requests library to perform a HTTP POST request to the remote server.

        :param reqs: GraphQL requests as a list of GraphQLRequest objects.
        :param timeout: Specifies a default timeout for requests (Default: None).
        :param extra_args: additional arguments to send to the requests post method
        :return: A list of results of execution.
            For every result `data` is the result of executing the query,
            `errors` is null if no errors occurred, and is a non-empty array
            if an error occurred.
        """

        if not self.session:
            raise TransportClosed("Transport is not connected")

        post_args = self._prepare_request(
            reqs,
            timeout=timeout,
            extra_args=extra_args,
        )

        try:
            response = self.session.request(
                self.method,
                self.url,
                **post_args,
            )
        except Exception as e:
            raise TransportConnectionFailed(str(e)) from e

        return self._prepare_batch_result(reqs, response)

    def _get_json_result(self, response: requests.Response) -> Any:

        # Saving latest response headers in the transport
        self.response_headers = response.headers

        try:
            result = self.json_deserialize(response.text)

            if log.isEnabledFor(logging.DEBUG):
                log.debug("<<< %s", response.text)

        except Exception:
            self._raise_response_error(response, "Not a JSON answer")

        return result

    def _prepare_result(self, response: requests.Response) -> ExecutionResult:

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
        response: requests.Response,
    ) -> List[ExecutionResult]:

        answers = self._get_json_result(response)

        try:
            return get_batch_execution_result_list(reqs, answers)
        except TransportProtocolError:
            # Raise a TransportServerError if status > 400
            self._raise_transport_server_error_if_status_more_than_400(response)
            # In other cases, raise a TransportProtocolError
            raise

    def close(self):
        """Closing the transport by closing the inner session"""
        if self.session:
            self.session.close()
            self.session = None
