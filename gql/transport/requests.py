import json
import logging
from typing import Any, Dict, Optional, Union

import requests
from graphql import DocumentNode, ExecutionResult, print_ast
from requests.adapters import HTTPAdapter, Retry
from requests.auth import AuthBase
from requests.cookies import RequestsCookieJar

from gql.transport import Transport

from .exceptions import (
    TransportAlreadyConnected,
    TransportClosed,
    TransportProtocolError,
    TransportServerError,
)

log = logging.getLogger(__name__)


class RequestsHTTPTransport(Transport):
    """:ref:`Sync Transport <sync_transports>` used to execute GraphQL queries
    on remote servers.

    The transport uses the requests library to send HTTP POST requests.
    """

    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, Any]] = None,
        cookies: Optional[Union[Dict[str, Any], RequestsCookieJar]] = None,
        auth: Optional[AuthBase] = None,
        use_json: bool = True,
        timeout: Optional[int] = None,
        verify: bool = True,
        retries: int = 0,
        method: str = "POST",
        **kwargs: Any,
    ):
        """Initialize the transport with the given request parameters.

        :param url: The GraphQL server URL.
        :param headers: Dictionary of HTTP Headers to send with the :class:`Request`
            (Default: None).
        :param cookies: Dict or CookieJar object to send with the :class:`Request`
            (Default: None).
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
        self.kwargs = kwargs

        self.session = None

    def connect(self):

        if self.session is None:

            # Creating a session that can later be re-use to configure custom mechanisms
            self.session = requests.Session()

            # If we specified some retries, we provide a predefined retry-logic
            if self.retries > 0:
                adapter = HTTPAdapter(
                    max_retries=Retry(
                        total=self.retries,
                        backoff_factor=0.1,
                        status_forcelist=[500, 502, 503, 504],
                    )
                )
                for prefix in "http://", "https://":
                    self.session.mount(prefix, adapter)
        else:
            raise TransportAlreadyConnected("Transport is already connected")

    def execute(  # type: ignore
        self,
        document: DocumentNode,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> ExecutionResult:
        """Execute GraphQL query.

        Execute the provided document AST against the configured remote server. This
        uses the requests library to perform a HTTP POST request to the remote server.

        :param document: GraphQL query as AST Node object.
        :param variable_values: Dictionary of input parameters (Default: None).
        :param operation_name: Name of the operation that shall be executed.
            Only required in multi-operation documents (Default: None).
        :param timeout: Specifies a default timeout for requests (Default: None).
        :return: The result of execution.
            `data` is the result of executing the query, `errors` is null
            if no errors occurred, and is a non-empty array if an error occurred.
        """

        if not self.session:
            raise TransportClosed("Transport is not connected")

        query_str = print_ast(document)
        payload: Dict[str, Any] = {"query": query_str}
        if variable_values:
            payload["variables"] = variable_values
        if operation_name:
            payload["operationName"] = operation_name

        data_key = "json" if self.use_json else "data"
        post_args = {
            "headers": self.headers,
            "auth": self.auth,
            "cookies": self.cookies,
            "timeout": timeout or self.default_timeout,
            "verify": self.verify,
            data_key: payload,
        }

        # Log the payload
        if log.isEnabledFor(logging.INFO):
            log.info(">>> %s", json.dumps(payload))

        # Pass kwargs to requests post method
        post_args.update(self.kwargs)

        # Using the created session to perform requests
        response = self.session.request(
            self.method, self.url, **post_args  # type: ignore
        )

        def raise_response_error(resp: requests.Response, reason: str):
            # We raise a TransportServerError if the status code is 400 or higher
            # We raise a TransportProtocolError in the other cases

            try:
                # Raise a HTTPError if response status is 400 or higher
                resp.raise_for_status()
            except requests.HTTPError as e:
                raise TransportServerError(str(e), e.response.status_code) from e

            result_text = resp.text
            raise TransportProtocolError(
                f"Server did not return a GraphQL result: "
                f"{reason}: "
                f"{result_text}"
            )

        try:
            result = response.json()

            if log.isEnabledFor(logging.INFO):
                log.info("<<< %s", response.text)

        except Exception:
            raise_response_error(response, "Not a JSON answer")

        if "errors" not in result and "data" not in result:
            raise_response_error(response, 'No "data" or "errors" keys in answer')

        return ExecutionResult(
            errors=result.get("errors"),
            data=result.get("data"),
            extensions=result.get("extensions"),
        )

    def close(self):
        """Closing the transport by closing the inner session"""
        if self.session:
            self.session.close()
            self.session = None
