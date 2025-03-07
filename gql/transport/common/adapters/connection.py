import abc
from typing import Dict


class AdapterConnection(abc.ABC):
    """Abstract interface for subscription connections.

    This allows different WebSocket implementations to be used interchangeably.
    """

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
            TransportConnectionClosed: If connection closed
        """
        pass  # pragma: no cover

    @abc.abstractmethod
    async def receive(self) -> str:
        """Receive message from the server.

        Returns:
            String message received

        Raises:
            TransportConnectionClosed: If connection closed
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
