import json
import logging
import re
from abc import ABC, abstractmethod
from base64 import b64encode
from ssl import SSLContext
from typing import Any, Callable, Dict, Optional, Tuple, Union, cast
from urllib.parse import urlparse

import botocore.session
from botocore.auth import BaseSigner, SigV4Auth
from botocore.awsrequest import AWSRequest, create_request_object
from botocore.credentials import Credentials
from botocore.exceptions import NoCredentialsError, NoRegionError
from botocore.session import get_session
from graphql import DocumentNode, ExecutionResult, print_ast

from .exceptions import TransportProtocolError, TransportServerError
from .websockets import WebsocketsTransport, WebsocketsTransportBase

log = logging.getLogger(__name__)


class AppSyncAuthentication(ABC):
    """AWS authentication abstract base class

    All AWS authentication class should have a
    :meth:`get_headers <gql.transport.appsync.AppSyncAuthentication.get_headers>`
    method which defines the headers used in the authentication process."""

    def get_auth_url(self, url: str) -> str:
        """
        :return: a url with base64 encoded headers used to establish
                 a websocket connection to the appsync-realtime-api.
        """
        headers = self.get_headers()

        encoded_headers = b64encode(
            json.dumps(headers, separators=(",", ":")).encode()
        ).decode()

        url_base = url.replace("https://", "wss://").replace(
            "appsync-api", "appsync-realtime-api"
        )

        return f"{url_base}?header={encoded_headers}&payload=e30="

    @abstractmethod
    def get_headers(self, data: Optional[str] = None) -> Dict:
        raise NotImplementedError()  # pragma: no cover


class AppSyncApiKeyAuthentication(AppSyncAuthentication):
    """AWS authentication class using an API key"""

    def __init__(self, host: str, api_key: str) -> None:
        """
        :param host: the host, something like:
                     XXXXXXXXXXXXXXXXXXXXXXXXXX.appsync-api.REGION.amazonaws.com
        :param api_key: the API key
        """
        self._host = host
        self.api_key = api_key

    def get_headers(self, data: Optional[str] = None) -> Dict:
        return {"host": self._host, "x-api-key": self.api_key}


class AppSyncJWTAuthentication(AppSyncAuthentication):
    """AWS authentication class using a JWT access token.

    It can be used either for:
     - Amazon Cognito user pools
     - OpenID Connect (OIDC)
    """

    def __init__(self, host: str, jwt: str) -> None:
        """
        :param host: the host, something like:
                     XXXXXXXXXXXXXXXXXXXXXXXXXX.appsync-api.REGION.amazonaws.com
        :param jwt: the JWT Access Token
        """
        self._host = host
        self.jwt = jwt

    def get_headers(self, data: Optional[str] = None) -> Dict:
        return {"host": self._host, "Authorization": self.jwt}


class AppSyncIAMAuthentication(AppSyncAuthentication):
    """AWS authentication class using IAM.

    .. note::
        There is no need for you to use this class directly, you could instead
        intantiate the :class:`gql.transport.appsync.AppSyncWebsocketsTransport`
        without an auth argument.

    During initialization, this class will use botocore to attempt to
    find your IAM credentials, either from environment variables or
    from your AWS credentials file.
    """

    def __init__(
        self,
        host: str,
        region_name: Optional[str] = None,
        signer: Optional[BaseSigner] = None,
        request_creator: Optional[Callable[[Dict[str, Any]], AWSRequest]] = None,
        credentials: Optional[Credentials] = None,
        session: Optional[botocore.session.Session] = None,
    ) -> None:
        """Initialize itself, saving the found credentials used
        to sign the headers later.

        if no credentials are found, then a NoCredentialsError is raised.
        """
        self._host = host
        self._session = session if session else get_session()
        self._credentials = (
            credentials if credentials else self._session.get_credentials()
        )
        self._service_name = "appsync"
        self._region_name = region_name or self._detect_region_name()
        self._signer = (
            signer
            if signer
            else SigV4Auth(self._credentials, self._service_name, self._region_name)
        )
        self._request_creator = (
            request_creator if request_creator else create_request_object
        )

    def _detect_region_name(self):
        """Try to detect the correct region_name.

        First try to extract the region_name from the host.

        If that does not work, then try to get the region_name from
        the aws configuration (~/.aws/config file) or the AWS_DEFAULT_REGION
        environment variable.

        If no region_name was found, then raise a NoRegionError exception."""

        # Regular expression from botocore.utils.validate_region
        m = re.search(
            r"appsync-api\.((?![0-9]+$)(?!-)[a-zA-Z0-9-]{,63}(?<!-))\.", self._host
        )

        if m:
            region_name = m.groups()[0]
            log.debug(f"Region name extracted from host: {region_name}")

        else:
            log.debug("Region name not found in host, trying default region name")
            region_name = self._session._resolve_region_name(
                None, self._session.get_default_client_config()
            )

        if region_name is None:
            raise NoRegionError

        return region_name

    def get_headers(self, data: Optional[str] = None,) -> Dict:

        headers = {
            "accept": "application/json, text/javascript",
            "content-encoding": "amz-1.0",
            "content-type": "application/json; charset=UTF-8",
        }

        request: AWSRequest = self._request_creator(
            {
                "method": "POST",
                "url": f"https://{self._host}/graphql{'' if data else '/connect'}",
                "headers": headers,
                "context": {},
                "body": data or "{}",
            }
        )

        self._signer.add_auth(request)

        headers = dict(request.headers)

        headers["host"] = self._host

        if log.isEnabledFor(logging.DEBUG):
            headers_log = []
            headers_log.append("\n\nSigned headers:")
            for key, value in headers.items():
                headers_log.append(f"    {key}: {value}")
            headers_log.append("\n")
            log.debug("\n".join(headers_log))

        return headers


class AppSyncWebsocketsTransport(WebsocketsTransportBase):
    """:ref:`Async Transport <async_transports>` used to execute GraphQL subscription on
    AWS appsync realtime endpoint.

    This transport uses asyncio and the websockets library in order to send requests
    on a websocket connection.
    """

    auth: Optional[AppSyncAuthentication]

    def __init__(
        self,
        url: str,
        auth: Optional[AppSyncAuthentication] = None,
        session: Optional[botocore.session.Session] = None,
        ssl: Union[SSLContext, bool] = False,
        connect_timeout: int = 10,
        close_timeout: int = 10,
        ack_timeout: int = 10,
        keep_alive_timeout: Optional[Union[int, float]] = None,
        connect_args: Dict[str, Any] = {},
    ) -> None:
        """Initialize the transport with the given parameters.

        :param url: The GraphQL endpoint URL. Example:
            https://XXXXXXXXXXXXXXXXXXXXXXXXXX.appsync-api.REGION.amazonaws.com/graphql
        :param auth: Optional AWS authentication class which will provide the
                     necessary headers to be correctly authenticated. If this
                     argument is not provided, then we will try to authenticate
                     using IAM.
        :param ssl: ssl_context of the connection.
        :param connect_timeout: Timeout in seconds for the establishment
            of the websocket connection. If None is provided this will wait forever.
        :param close_timeout: Timeout in seconds for the close. If None is provided
            this will wait forever.
        :param ack_timeout: Timeout in seconds to wait for the connection_ack message
            from the server. If None is provided this will wait forever.
        :param keep_alive_timeout: Optional Timeout in seconds to receive
            a sign of liveness from the server.
        :param connect_args: Other parameters forwarded to websockets.connect
        """
        try:
            if not auth:

                # Extract host from url
                host = str(urlparse(url).netloc)

                auth = AppSyncIAMAuthentication(host=host, session=session)

            self.auth = auth

            url = self.auth.get_auth_url(url)

        except NoCredentialsError:
            log.warning(
                "Credentials not found. "
                "Do you have default AWS credentials configured?",
            )
            raise
        except NoRegionError:
            log.warning(
                "Region name not found. "
                "It was not possible to detect your region either from the host "
                "or from your default AWS configuration."
            )
            raise

        super().__init__(
            url,
            ssl=ssl,
            connect_timeout=connect_timeout,
            close_timeout=close_timeout,
            ack_timeout=ack_timeout,
            keep_alive_timeout=keep_alive_timeout,
            connect_args=connect_args,
        )

        # Using the same 'graphql-ws' protocol as the apollo protocol
        self.supported_subprotocols = [
            WebsocketsTransport.APOLLO_SUBPROTOCOL,
        ]
        self.subprotocol = WebsocketsTransport.APOLLO_SUBPROTOCOL

    def _parse_answer(
        self, answer: str
    ) -> Tuple[str, Optional[int], Optional[ExecutionResult]]:
        """Parse the answer received from the server.

        Difference between apollo protocol and aws protocol:

        - aws protocol can return an error without an id
        - aws protocol will send start_ack messages

        Returns a list consisting of:
            - the answer_type:
              - 'connection_ack',
              - 'connection_error',
              - 'start_ack',
              - 'ka',
              - 'data',
              - 'error',
              - 'complete'
            - the answer id (Integer) if received or None
            - an execution Result if the answer_type is 'data' or None
        """

        answer_type: str = ""

        try:
            json_answer = json.loads(answer)

            answer_type = str(json_answer.get("type"))

            if answer_type == "start_ack":
                return ("start_ack", None, None)

            elif answer_type == "error" and "id" not in json_answer:
                error_payload = json_answer.get("payload")
                raise TransportServerError(f"Server error: '{error_payload!r}'")

            else:

                return WebsocketsTransport._parse_answer_apollo(
                    cast(WebsocketsTransport, self), json_answer
                )

        except ValueError:
            raise TransportProtocolError(
                f"Server did not return a GraphQL result: {answer}"
            )

    async def _send_query(
        self,
        document: DocumentNode,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
    ) -> int:

        query_id = self.next_query_id

        self.next_query_id += 1

        data: Dict = {"query": print_ast(document)}

        if variable_values:
            data["variables"] = variable_values

        if operation_name:
            data["operationName"] = operation_name

        serialized_data = json.dumps(data, separators=(",", ":"))

        payload = {"data": serialized_data}

        message: Dict = {
            "id": str(query_id),
            "type": "start",
            "payload": payload,
        }

        assert self.auth is not None

        message["payload"]["extensions"] = {
            "authorization": self.auth.get_headers(serialized_data)
        }

        await self._send(json.dumps(message, separators=(",", ":"),))

        return query_id

    subscribe = WebsocketsTransportBase.subscribe
    """Send a subscription query and receive the results using
    a python async generator.

    Only subscriptions are supported, queries and mutations are forbidden.

    The results are sent as an ExecutionResult object.
    """

    async def execute(
        self,
        document: DocumentNode,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
    ) -> ExecutionResult:
        """This method is not available.

        Only subscriptions are supported on the AWS realtime endpoint.

        :raise: AssertionError"""
        raise AssertionError(
            "execute method is not allowed for AppSyncWebsocketsTransport "
            "because only subscriptions are allowed on the realtime endpoint."
        )

    _initialize = WebsocketsTransport._initialize
    _stop_listener = WebsocketsTransport._stop_listener  # type: ignore
    _send_init_message_and_wait_ack = (
        WebsocketsTransport._send_init_message_and_wait_ack
    )
    _wait_ack = WebsocketsTransport._wait_ack
