import json
import logging
from abc import ABC, abstractmethod
from base64 import b64encode
from ssl import SSLContext
from typing import Any, Callable, Dict, Optional, Tuple, Union
from urllib.parse import urlparse

import botocore.session
from botocore.auth import BaseSigner, SigV4Auth
from botocore.awsrequest import AWSRequest, create_request_object
from botocore.credentials import Credentials
from botocore.exceptions import NoCredentialsError
from botocore.session import get_session
from graphql import DocumentNode, ExecutionResult, print_ast

from .exceptions import TransportProtocolError, TransportServerError
from .websockets import WebsocketsTransport

log = logging.getLogger(__name__)


class AppSyncAuthorization(ABC):
    def get_auth_url(self, url: str) -> str:
        """
        :return: a url used to establish websocket connections
                 to the appsync-realtime-api
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
        raise NotImplementedError()


class AppSyncApiKeyAuthorization(AppSyncAuthorization):
    def __init__(self, host: str, api_key: str) -> None:
        self._host = host
        self.api_key = api_key

    def get_headers(self, data: Optional[str] = None) -> Dict:
        return {"host": self._host, "x-api-key": self.api_key}


class AppSyncOIDCAuthorization(AppSyncAuthorization):
    def __init__(self, host: str, jwt: str) -> None:
        self._host = host
        self.jwt = jwt

    def get_headers(self, data: Optional[str] = None) -> Dict:
        return {"host": self._host, "Authorization": self.jwt}


class AppSyncCognitoUserPoolAuthorization(AppSyncOIDCAuthorization):
    """Alias for AppSyncOIDCAuthorization"""

    pass


class AppSyncIAMAuthorization(AppSyncAuthorization):
    def __init__(
        self,
        host: str,
        region_name: Optional[str] = None,
        signer: Optional[BaseSigner] = None,
        request_creator: Optional[Callable[[Dict[str, Any]], AWSRequest]] = None,
        credentials: Optional[Credentials] = None,
        session: Optional[botocore.session.Session] = None,
    ) -> None:
        self._host = host
        self._session = session if session else get_session()
        self._credentials = (
            credentials if credentials else self._session.get_credentials()
        )
        self._region_name = self._session._resolve_region_name(
            region_name, self._session.get_default_client_config()
        )
        self._service_name = "appsync"
        self._signer = (
            signer
            if signer
            else SigV4Auth(self._credentials, self._service_name, self._region_name)
        )
        self._request_creator = (
            request_creator if request_creator else create_request_object
        )

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


class AppSyncWebsocketsTransport(WebsocketsTransport):
    authorization: Optional[AppSyncAuthorization]

    def __init__(
        self,
        url: str,
        authorization: Optional[AppSyncAuthorization] = None,
        session: Optional[botocore.session.Session] = None,
        ssl: Union[SSLContext, bool] = False,
        connect_timeout: int = 10,
        close_timeout: int = 10,
        ack_timeout: int = 10,
        connect_args: Dict[str, Any] = {},
    ) -> None:
        try:
            if not authorization:

                # Extract host from url
                host = str(urlparse(url).netloc)

                authorization = AppSyncIAMAuthorization(host=host, session=session)

            self.authorization = authorization

            url = self.authorization.get_auth_url(url)

        except NoCredentialsError:
            log.warning(
                "Credentials not found.  "
                "Do you have default AWS credentials configured?",
            )
            raise
        except TypeError:
            log.warning(
                "A TypeError was raised.  "
                "The most likely reason for this is that the AWS "
                "region is missing from the credentials.",
            )
            raise

        super().__init__(
            url,
            ssl=ssl,
            connect_timeout=connect_timeout,
            close_timeout=close_timeout,
            ack_timeout=ack_timeout,
            connect_args=connect_args,
        )

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
        answer_id: Optional[int] = None
        execution_result: Optional[ExecutionResult] = None

        try:
            json_answer = json.loads(answer)

            answer_type = str(json_answer.get("type"))

            if answer_type == "start_ack":
                return ("start_ack", None, None)

            elif answer_type == "error" and id not in json_answer:
                error_payload = json_answer.get("payload")
                raise TransportServerError(f"Server error: '{error_payload!r}'")

            else:

                return self._parse_answer_apollo(answer)

        except ValueError as e:
            raise TransportProtocolError(
                f"Server did not return a GraphQL result: {answer}"
            ) from e

        return answer_type, answer_id, execution_result

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

        assert self.authorization is not None

        message["payload"]["extensions"] = {
            "authorization": self.authorization.get_headers(serialized_data)
        }

        await self._send(json.dumps(message, separators=(",", ":"),))

        return query_id
