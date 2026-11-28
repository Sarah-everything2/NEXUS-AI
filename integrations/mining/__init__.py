"""Universal multi-miner framework."""

from .models import MinerCapabilities
from .registry import MinerRegistry, create_default_registry

__all__ = [
    "MinerCapabilities",
    "MinerRegistry",
    "create_default_registry",
]
