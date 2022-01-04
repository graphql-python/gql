"""Compatibility helpers to smooth over differences between Python versions."""
import sys

# Load the appropriate instance of the Literal type
if sys.version_info[:2] >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

__all__ = ["Literal"]
