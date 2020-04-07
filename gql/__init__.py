import sys

from .gql import gql
from .client import Client

__all__ = ["gql", "Client"]

if sys.version_info > (3, 6):
    from .async_client import AsyncClient

    # Cannot use __all__.append here because of flake8 warning
    __all__ = ["gql", "Client", "AsyncClient"]
