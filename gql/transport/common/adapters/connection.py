import abc
from typing import Any, Dict, List, Optional


class AdapterConnection(abc.ABC):
    """Abstract interface for subscription connections.

    This allows different WebSocket implementations to be used interchangeably.
    """

    url: str
    connect_args: Dict[str, Any]
    subprotocols: Optional[List[str]]

    def __init__(self, url: str, connect_args: Optional[Dict[str, Any]]):
        """Initialize the connection adapter."""
        self.url: str = url

        if connect_args is None:
            connect_args = {}
        self.connect_args = connect_args

        self.subprotocols = None

    @abc.abstractmethod
    async def connect(self) -> None:
        """Connect to the server."""
        pass  # pragma: no cover

    @abc.abstractmethod
    async def send(self, message: str) -> None:
        """Send message to the server.

        Args:
            message: String message to send

        Raises:
            TransportConnectionFailed: If connection closed
        """
        pass  # pragma: no cover

    @abc.abstractmethod
    async def receive(self) -> str:
        """Receive message from the server.

        Returns:
            String message received

        Raises:
            TransportConnectionFailed: If connection closed
            TransportProtocolError: If protocol error or binary data received
        """
        pass  # pragma: no cover

    @abc.abstractmethod
    async def close(self) -> None:
        """Close the connection."""
        pass  # pragma: no cover

    @property
    @abc.abstractmethod
    def response_headers(self) -> Dict[str, str]:
        """Get the response headers from the connection.

        Returns:
            Dictionary of response headers
        """
        pass  # pragma: no cover
