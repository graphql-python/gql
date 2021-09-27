from asyncio import wait_for, ensure_future

from graphql import DocumentNode, print_ast

from .exceptions import TransportProtocolError
from .websockets import WebsocketsTransport
from ssl import SSLContext
from typing import Any, Dict, Union, Optional
from abc import ABC, abstractmethod
from base64 import b64encode
from botocore.awsrequest import AWSRequest, create_request_object
from botocore.session import Session
from botocore.auth import SigV4Auth
import json


class AppSyncAuthorization(ABC):
    def __init__(self, host: str):
        self._host = host

    def host_to_auth_url(self) -> str:
        """Munge Host For Appsync Auth

        :return: a url used to establish websocket connections to the appsync-realtime-api
        """
        url_after_replacements=self._host.replace("https", "wss").replace("appsync-api", "appsync-realtime-api")
        headers_from_auth=self.get_headers()
        encoded_headers = b64encode(
            json.dumps(headers_from_auth, separators=(",", ":")).encode()
        ).decode()
        return '{url}?header={headers}&payload=e30='.format(
            url=url_after_replacements,
            headers=encoded_headers
        )

    @abstractmethod
    def get_headers(self, data: Optional[str] = None) -> Dict:
        raise NotImplementedError()


class AppSyncApiKeyAuthorization(AppSyncAuthorization):
    def __init__(self, host: str, api_key: str) -> None:
        super().__init__(host)
        self.api_key = api_key

    def get_headers(self, data: Optional[str] = None) -> Dict:
        return {"host": self._host, "x-api-key": self.api_key}


class AppSyncOIDCAuthorization(AppSyncAuthorization):
    def __init__(self, host: str, jwt: str) -> None:
        super().__init__(host)
        self.jwt = jwt

    def get_headers(self, data: Optional[str] = None) -> Dict:
        return {"host": self._host, "Authorization": self.jwt}



class AppSyncCognitoUserPoolAuthorization(AppSyncOIDCAuthorization):
    """Alias for AppSyncOIDCAuthorization"""
    pass


class AppSyncIAMAuthorization(AppSyncAuthorization):
    def __init__(self, host: str, region_name=None, profile=None, signer=None, request_creator=None) -> None:
        super().__init__(host)
        self._session = Session(profile=profile)
        self._credentials = self._session.get_credentials()
        self._region_name = self._session._resolve_region_name(region_name, self._session.get_default_client_config())
        self._service_name = "appsync"
        self._signer = signer if signer else SigV4Auth(self._credentials, self._service_name, self._region_name)
        self._request_creator = request_creator if request_creator else create_request_object

    def get_headers(self, data: Optional[str] = None, request_creator: callable = None) -> Dict:
        request = self._request_creator({
            'method': 'GET',
            'url': self._host,
            'headers': {},
            'context': {},
            'body': data,
        })
        self._signer.add_auth(request)
        return request.headers


class AppSyncWebsocketsTransport(WebsocketsTransport):
    def __init__(
        self,
        url: str,
        authorization: AppSyncAuthorization = None,
        ssl: Union[SSLContext, bool] = False,
        connect_timeout: int = 10,
        close_timeout: int = 10,
        ack_timeout: int = 10,
        connect_args: Dict[str, Any] = {},
    ) -> None:
        self.authorization = authorization if authorization else AppSyncIAMAuthorization(host=url)
        url = self.authorization.host_to_auth_url()
        super().__init__(
            url,
            ssl=ssl,
            connect_timeout=connect_timeout,
            close_timeout=close_timeout,
            ack_timeout=ack_timeout,
            connect_args=connect_args,
        )

    async def _wait_start_ack(self) -> None:
        """Wait for the start_ack message. Keep alive messages are ignored"""

        while True:
            answer_type = str(json.loads(await self._receive()).get("type"))

            if answer_type == "start_ack":
                return

            if answer_type != "ka":
                raise TransportProtocolError(
                    "AppSync server did not return a start ack"
                )

    async def _send_query(
        self,
        document: DocumentNode,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
    ) -> int:
        query_id = self.next_query_id
        self.next_query_id += 1

        data = {"query": print_ast(document)}
        if variable_values:
            data["variables"] = variable_values
        if operation_name:
            data["operationName"] = operation_name

        await self._send(
            json.dumps(
                {
                    "id": str(query_id),
                    "type": "start",
                    "payload": {
                        "data": data,
                        "extensions": {
                            "authorization": self.authorization.get_headers(data)
                        }
                    }
                },
                separators=(",", ":"),
            )
        )

        return query_id
