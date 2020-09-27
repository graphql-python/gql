"""The primary :mod:`gql` package includes everything you need to
execute GraphQL requests:

 - the :func:`gql <gql.gql>` method to parse a GraphQL query
 - the :class:`Client <gql.Client>` class as the entrypoint to execute requests
   and create sessions
 - all the transports classes implementing different communication protocols
"""

from .__version__ import __version__
from .client import Client
from .gql import gql
from .transport.aiohttp import AIOHTTPTransport
from .transport.phoenix_channel_websockets import PhoenixChannelWebsocketsTransport
from .transport.requests import RequestsHTTPTransport
from .transport.websockets import WebsocketsTransport

__all__ = [
    "__version__",
    "gql",
    "AIOHTTPTransport",
    "Client",
    "PhoenixChannelWebsocketsTransport",
    "RequestsHTTPTransport",
    "WebsocketsTransport",
]
