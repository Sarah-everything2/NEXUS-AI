"""Tests for the universal mining adapter registry."""

import pytest

from integrations.mining.base import MinerAdapter
from integrations.mining.models import MinerCapabilities
from integrations.mining.registry import (
    MinerRegistry,
    create_default_registry,
)


class FakeMiner(MinerAdapter):
    name = "fake"

    @property
    def capabilities(self):
        return MinerCapabilities(
            engine="fake",
            algorithms=("example-algo",),
            coins=("EXAMPLE",),
            features=("start", "stop"),
            verified=True,
        )

    def status(self):
        return {"status": "STOPPED"}

    def health(self):
        return {"healthy": True}

    def start(self, profitability_decision=None):
        return {"status": "START_REQUESTED"}

    def stop(self):
        return {"status": "STOPPED"}

    def recover(self, profitability_decision=None):
        return {"status": "IDLE"}


def test_register_and_lookup_adapter():
    registry = MinerRegistry()
    adapter = FakeMiner()

    registry.register(adapter)

    assert registry.get("fake") is adapter
    assert registry.require("FAKE") is adapter


def test_duplicate_registration_is_rejected():
    registry = MinerRegistry()
    registry.register(FakeMiner())

    with pytest.raises(ValueError):
        registry.register(FakeMiner())


def test_unverified_algorithm_is_not_compatible():
    registry = create_default_registry()

    assert registry.compatible("random-algorithm") == []


def test_verified_algorithm_is_compatible():
    registry = MinerRegistry()
    adapter = FakeMiner()
    registry.register(adapter)

    assert registry.compatible("EXAMPLE-ALGO") == [adapter]


def test_default_registry_contains_xmrig_without_starting_it():
    registry = create_default_registry()
    adapter = registry.get("xmrig")

    assert adapter is not None
    assert adapter.name == "xmrig"
    assert adapter.status()["status"] in ("RUNNING", "STOPPED")


def test_unregistered_engine_returns_none():
    assert MinerRegistry().get("unknown") is None
