import sys

from .transport import Transport

__all__ = ["Transport"]


if sys.version_info > (3, 6):
    from .async_transport import AsyncTransport

    # Cannot use __all__.append here because of flake8 warning
    __all__ = ["Transport", "AsyncTransport"]
