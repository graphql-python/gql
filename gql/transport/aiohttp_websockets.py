from enum import verify
import re
import time
import aiohttp
from gql.transport.async_transport import AsyncTransport
from typing import Optional, Union, Collection
from aiohttp.typedefs import LooseHeaders, Mapping, StrOrURL
from aiohttp.helpers import hdrs, BasicAuth, _SENTINEL

"""HTTP Client for asyncio."""

from typing import (
    Collection,
    Mapping,
    Optional,
    Union,
)


from aiohttp import hdrs
from aiohttp.client_reqrep import (
    Fingerprint,
)
from aiohttp.helpers import (
    _SENTINEL,
    BasicAuth,
    sentinel,
)
from aiohttp.typedefs import LooseHeaders, StrOrURL

from ssl import SSLContext


class AIOHTTPWebsocketsTransport(AsyncTransport):

    def __init__(
        self,
        url: StrOrURL,
        *,
        method: str = hdrs.METH_GET,
        protocols: Collection[str] = (),
        timeout: Union[float, _SENTINEL, None] = sentinel,
        receive_timeout: Optional[float] = None,
        autoclose: bool = True,
        autoping: bool = True,
        heartbeat: Optional[float] = None,
        auth: Optional[BasicAuth] = None,
        origin: Optional[str] = None,
        params: Optional[Mapping[str, str]] = None,
        headers: Optional[LooseHeaders] = None,
        proxy: Optional[StrOrURL] = None,
        proxy_auth: Optional[BasicAuth] = None,
        ssl: Union[SSLContext, bool, Fingerprint] = True,
        ssl_context: Optional[SSLContext] = None,
        verify_ssl: Optional[bool] = True,
        server_hostname: Optional[str] = None,
        proxy_headers: Optional[LooseHeaders] = None,
        compress: int = 0,
        max_msg_size: int = 4 * 1024 * 1024,
    ) -> None:
        self.url: str = url
        self.headers: Optional[LooseHeaders] = headers
        self.auth: Optional[BasicAuth] = auth
        self.autoclose: bool = autoclose
        self.autoping: bool = autoping
        self.compress: int = compress
        self.heartbeat: Optional[float] = heartbeat
        self.max_msg_size: int = max_msg_size
        self.method: str = method
        self.origin: Optional[str] = origin
        self.params: Optional[Mapping[str, str]] = params
        self.protocols: Optional[list[str]] = protocols
        self.proxy: Optional[StrOrURL] = proxy
        self.proxy_auth: Optional[BasicAuth] = proxy_auth
        self.proxy_headers: Optional[LooseHeaders] = proxy_headers
        self.receive_timeout: Optional[float] = receive_timeout
        self.ssl: Union[SSLContext, bool] = ssl
        self.ssl_context: Optional[SSLContext] = ssl_context
        self.timeout: Union[float, _SENTINEL, None] = timeout        
        self.verify_ssl: Optional[bool] = verify_ssl


        self.session: Optional[aiohttp.ClientSession] = None
        self.websocket: Optional[aiohttp.ClientWebSocketResponse] = None

        super().__init__()

    async def connect(self) -> None:
        if self.session is None:
            self.session = aiohttp.ClientSession()

        if self.session is not None:
            try:
                self.websocket = await self.session.ws_connect(
                    method=self.method,
                    url=self.url,
                    headers=self.headers,
                    auth=self.auth,
                    autoclose=self.autoclose,
                    autoping=self.autoping,
                    compress=self.compress,
                    heartbeat=self.heartbeat,
                    max_msg_size=self.max_msg_size,
                    origin=self.origin,
                    params=self.params,
                    protocols=self.protocols,
                    proxy=self.proxy,
                    proxy_auth=self.proxy_auth,
                    proxy_headers=self.proxy_headers,
                    receive_timeout=self.receive_timeout,
                    ssl=self.ssl,
                    ssl_context=None,
                    receive_timeout=self.receive_timeout,
                    timeout=self.timeout,
                    verify_ssl=self.verify_ssl,
                )
            except Exception as e:
                raise e
            finally:
                ...

    async def close(self): ...

    async def execute(self, document, variable_values=None, operation_name=None): ...

    def subscribe(self, document, variable_values=None, operation_name=None): ...
