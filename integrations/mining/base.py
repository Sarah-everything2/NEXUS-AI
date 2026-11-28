"""Contract that every mining engine adapter must implement."""

from abc import ABC, abstractmethod

from .models import MinerCapabilities


class MinerAdapter(ABC):
    @property
    @abstractmethod
    def name(self):
        """Return the unique engine identifier."""

    @property
    @abstractmethod
    def capabilities(self) -> MinerCapabilities:
        """Return verified or explicitly unverified capabilities."""

    @abstractmethod
    def status(self):
        """Return the engine's current process status."""

    @abstractmethod
    def health(self):
        """Return engine and system health information."""

    @abstractmethod
    def start(self, profitability_decision=None):
        """Start only through the engine's own safety checks."""

    @abstractmethod
    def stop(self):
        """Safely stop this engine."""

    @abstractmethod
    def recover(self, profitability_decision=None):
        """Run this engine's recovery procedure."""

    def logs(self, lines=30):
        raise NotImplementedError("Log retrieval is not supported.")

    def configure(self, **kwargs):
        raise NotImplementedError("Configuration is not supported.")
