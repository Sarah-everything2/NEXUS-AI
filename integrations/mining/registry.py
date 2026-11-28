"""Thread-safe registry for mining engine adapters."""

from threading import RLock

from .base import MinerAdapter


class MinerRegistry:
    def __init__(self):
        self._adapters = {}
        self._lock = RLock()

    def register(self, adapter, replace=False):
        if not isinstance(adapter, MinerAdapter):
            raise TypeError("Adapter must implement MinerAdapter.")

        name = adapter.name
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Adapter name must be non-empty.")

        name = name.strip().casefold()

        with self._lock:
            if name in self._adapters and not replace:
                raise ValueError(f"Miner adapter already registered: {name}")
            self._adapters[name] = adapter

        return adapter

    def unregister(self, name):
        if not isinstance(name, str):
            raise TypeError("Miner name must be a string.")

        with self._lock:
            return self._adapters.pop(name.strip().casefold(), None)

    def get(self, name):
        if not isinstance(name, str):
            return None

        with self._lock:
            return self._adapters.get(name.strip().casefold())

    def require(self, name):
        adapter = self.get(name)
        if adapter is None:
            raise KeyError(f"Unknown mining engine: {name}")
        return adapter

    def list(self):
        with self._lock:
            return [
                {
                    "name": adapter.name,
                    "capabilities": adapter.capabilities,
                }
                for _, adapter in sorted(self._adapters.items())
            ]

    def compatible(self, algorithm):
        """Return only engines with explicitly verified algorithm support."""
        with self._lock:
            return [
                adapter
                for adapter in self._adapters.values()
                if adapter.capabilities.supports_algorithm(algorithm)
            ]


def create_default_registry():
    """Build the default registry without starting any miner."""
    from .adapters.xmrig import XMRigAdapter
    from .adapters.cpuminer_opt import CpuMinerOptAdapter
    from .adapters.srbminer import SRBMinerAdapter

    registry = MinerRegistry()
    registry.register(XMRigAdapter())
    registry.register(CpuMinerOptAdapter())
    registry.register(SRBMinerAdapter())
    return registry
