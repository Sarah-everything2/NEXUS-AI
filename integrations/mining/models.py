"""Shared data models for mining engines."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MinerCapabilities:
    engine: str
    algorithms: tuple = ()
    coins: tuple = ()
    features: tuple = ()
    verified: bool = False

    def __post_init__(self):
        if not isinstance(self.engine, str) or not self.engine.strip():
            raise ValueError("Miner engine name must be non-empty.")

        for field_name in ("algorithms", "coins", "features"):
            value = getattr(self, field_name)
            if not isinstance(value, tuple):
                raise TypeError(f"{field_name} must be a tuple.")
            if any(not isinstance(item, str) or not item.strip()
                   for item in value):
                raise ValueError(f"{field_name} contains an invalid entry.")

        if not isinstance(self.verified, bool):
            raise TypeError("verified must be a boolean.")

    def supports_algorithm(self, algorithm):
        if not self.verified or not isinstance(algorithm, str):
            return False

        wanted = algorithm.strip().casefold()
        return bool(wanted) and any(
            item.casefold() == wanted for item in self.algorithms
        )
