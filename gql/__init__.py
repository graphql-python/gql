import sys

from .gql import gql

if sys.version_info > (3, 6):
    from .async_client import AsyncClient as Client
else:
    from .client import Client

__all__ = ["gql", "Client"]
