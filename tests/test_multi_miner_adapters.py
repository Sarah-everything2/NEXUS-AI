"""Offline tests for cpuminer-opt and SRBMiner adapters."""

import pytest

from integrations.mining.adapters.cpuminer_opt import CpuMinerOptAdapter
from integrations.mining.adapters.srbminer import SRBMinerAdapter
from integrations.mining.external import validate_config
from integrations.mining.registry import create_default_registry


CONFIG = {
    "coin": "TEST",
    "algorithm": "test-algo",
    "pool": "stratum+tcp://pool.example:3333",
    "wallet": "test-wallet",
    "password": "x",
    "threads": 1,
}


def test_cpuminer_opt_command_uses_documented_cpu_options():
    adapter = CpuMinerOptAdapter()
    command = adapter.build_command(CONFIG)

    assert command[1:] == [
        "-a", "test-algo",
        "-o", "stratum+tcp://pool.example:3333",
        "-u", "test-wallet",
        "-p", "x",
        "-t", "1",
    ]


def test_srbminer_command_explicitly_disables_gpu():
    adapter = SRBMinerAdapter()
    command = adapter.build_command(CONFIG)

    assert "--algorithm-cpu" in command
    assert "--cpu-threads" in command
    assert "--disable-gpu" in command
    assert "--disable-cpu" not in command


def test_registry_registers_all_three_engines():
    registry = create_default_registry()

    assert registry.get("xmrig") is not None
    assert registry.get("cpuminer-opt") is not None
    assert registry.get("srbminer-multi") is not None


def test_new_engines_do_not_claim_unverified_algorithms():
    registry = create_default_registry()

    assert registry.compatible("test-algo") == []


def test_valid_configuration_is_normalized():
    assert validate_config(CONFIG) == CONFIG


@pytest.mark.parametrize("bad_pool", [
    "pool.example:3333",
    "file://pool.example:3333",
    "stratum+tcp://pool.example",
    "stratum+tcp://",
])
def test_invalid_pool_is_rejected(bad_pool):
    config = dict(CONFIG, pool=bad_pool)
    with pytest.raises(ValueError):
        validate_config(config)


def test_invalid_thread_count_is_rejected():
    config = dict(CONFIG, threads=0)
    with pytest.raises(ValueError):
        validate_config(config)


def test_invalid_algorithm_is_rejected():
    config = dict(CONFIG, algorithm="algo;--unexpected")
    with pytest.raises(ValueError):
        validate_config(config)

def test_external_process_lock_creates_shared_lock_file(tmp_path, monkeypatch):
    from integrations.mining import external

    monkeypatch.setattr(external, "CONFIG_DIR", tmp_path)
    adapter = CpuMinerOptAdapter()

    with adapter._process_lock():
        lock_path = tmp_path / ".external-miners.lock"
        assert lock_path.is_file()
        assert lock_path.stat().st_size >= 1


def test_external_start_coordination_blocks_unknown_other_engine(monkeypatch):
    from integrations.mining import external
    from integrations.mining import registry as registry_module

    class FakeOther:
        def status(self):
            return {"status": "UNKNOWN"}

    class FakeRegistry:
        def get(self, name):
            return FakeOther() if name == "srbminer-multi" else None

    monkeypatch.setattr(
        registry_module,
        "create_default_registry",
        lambda: FakeRegistry(),
    )

    adapter = CpuMinerOptAdapter()

    with pytest.raises(RuntimeError, match="status is UNKNOWN"):
        adapter._ensure_no_other_external_miner()




def _prepare_external_recovery_test(tmp_path, monkeypatch):
    from integrations.mining import external
    from integrations.mining.adapters.cpuminer_opt import CpuMinerOptAdapter

    monkeypatch.setattr(external, "ROOT", tmp_path)
    monkeypatch.setattr(external, "CONFIG_DIR", tmp_path / "config" / "mining")
    monkeypatch.setattr(external, "STATE_DIR", tmp_path / "config" / "mining" / "state")

    policy_path = tmp_path / "config" / "xmrig.policy.json"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    external.save_json(policy_path, {
        "mining_enabled": True,
        "autonomous_execution_enabled": True,
        "autonomous_restart_enabled": True,
        "stop_when_unprofitable": True,
        "maximum_restarts_per_hour": 3,
    })

    adapter = CpuMinerOptAdapter()
    adapter.state_path.parent.mkdir(parents=True, exist_ok=True)
    external.save_json(adapter.state_path, {
        "engine": adapter.engine,
        "pid": 45678,
        "executable": str(adapter.executable),
        "started_at": 1.0,
    })

    monkeypatch.setattr(adapter, "load_config", lambda: {
        "coin": "TEST",
        "algorithm": "test-algo",
        "pool": "stratum+tcp://pool.example:3333",
        "wallet": "test-wallet",
        "password": "x",
        "threads": 1,
    })
    monkeypatch.setattr(adapter, "_inspect_process", lambda pid: ("EXITED", None))
    monkeypatch.setattr(adapter, "_validate_decision", lambda decision, config: None)
    monkeypatch.setattr(adapter, "_safety_check", lambda: {"telemetry_complete": True})
    return external, adapter


def test_external_recovery_records_attempt_and_preserves_old_state(tmp_path, monkeypatch):
    external, adapter = _prepare_external_recovery_test(tmp_path, monkeypatch)
    decision = {"test": True}
    observed = {}

    def fake_start(received):
        observed["state_exists"] = adapter.state_path.is_file()
        observed["decision"] = received
        return {"status": "MOCK_STARTED", "engine": adapter.engine}

    monkeypatch.setattr(adapter, "start", fake_start)

    result = adapter.recover(decision)

    assert result["status"] == "MOCK_STARTED"
    assert observed["state_exists"] is True
    assert observed["decision"] is decision
    history = external.read_json(
        external.STATE_DIR / f"{adapter.engine}.recovery.json", {}
    )
    assert len(history["attempts"]) == 1
    assert external.read_json(adapter.state_path, {})["pid"] == 45678


def test_external_recovery_counts_failed_launch_and_preserves_state(tmp_path, monkeypatch):
    external, adapter = _prepare_external_recovery_test(tmp_path, monkeypatch)

    def failed_start(_decision):
        raise RuntimeError("Mock launch failure")

    monkeypatch.setattr(adapter, "start", failed_start)

    try:
        adapter.recover({"test": True})
    except RuntimeError as exc:
        assert "Mock launch failure" in str(exc)
    else:
        raise AssertionError("Expected mocked launch failure.")

    history = external.read_json(
        external.STATE_DIR / f"{adapter.engine}.recovery.json", {}
    )
    assert len(history["attempts"]) == 1
    assert external.read_json(adapter.state_path, {})["pid"] == 45678


def test_external_recovery_blocks_when_restart_policy_disabled(tmp_path, monkeypatch):
    external, adapter = _prepare_external_recovery_test(tmp_path, monkeypatch)
    policy_path = tmp_path / "config" / "xmrig.policy.json"
    policy = external.read_json(policy_path, {})
    policy["autonomous_restart_enabled"] = False
    external.save_json(policy_path, policy)

    result = adapter.recover({"test": True})

    assert result["status"] == "RESTART_BLOCKED"
    assert "autonomous restart" in result["reason"]
    assert external.read_json(adapter.state_path, {})["pid"] == 45678


def test_external_recovery_blocks_unknown_previous_process(tmp_path, monkeypatch):
    external, adapter = _prepare_external_recovery_test(tmp_path, monkeypatch)
    monkeypatch.setattr(adapter, "_inspect_process", lambda pid: ("UNKNOWN", None))

    result = adapter.recover({"test": True})

    assert result["status"] == "RECOVERY_BLOCKED"
    assert "verified" in result["reason"].lower() or "uncertain" in result["reason"].lower()
    assert not (external.STATE_DIR / f"{adapter.engine}.recovery.json").exists()
    assert external.read_json(adapter.state_path, {})["pid"] == 45678



def test_external_recovery_blocks_when_hourly_limit_is_reached(tmp_path, monkeypatch):
    external, adapter = _prepare_external_recovery_test(tmp_path, monkeypatch)
    recovery_path = external.STATE_DIR / f"{adapter.engine}.recovery.json"
    now = external.time.time()
    external.save_json(recovery_path, {
        "engine": adapter.engine,
        "attempts": [now - 100, now - 200, now - 300],
    })

    def unexpected_start(_decision):
        raise AssertionError("Recovery must not launch after the hourly limit.")

    monkeypatch.setattr(adapter, "start", unexpected_start)
    result = adapter.recover({"test": True})

    assert result["status"] == "RESTART_BLOCKED"
    assert "Hourly restart limit" in result["reason"]
    assert len(external.read_json(recovery_path, {})["attempts"]) == 3
    assert external.read_json(adapter.state_path, {})["pid"] == 45678


def test_external_recovery_blocks_malformed_history(tmp_path, monkeypatch):
    external, adapter = _prepare_external_recovery_test(tmp_path, monkeypatch)
    recovery_path = external.STATE_DIR / f"{adapter.engine}.recovery.json"
    external.save_json(recovery_path, {"engine": adapter.engine, "attempts": "invalid"})

    def unexpected_start(_decision):
        raise AssertionError("Recovery must not launch with malformed history.")

    monkeypatch.setattr(adapter, "start", unexpected_start)
    result = adapter.recover({"test": True})

    assert result["status"] == "RESTART_BLOCKED"
    assert "malformed" in result["reason"].lower()
    assert external.read_json(recovery_path, {})["attempts"] == "invalid"
    assert external.read_json(adapter.state_path, {})["pid"] == 45678


def test_external_recovery_blocks_when_policy_is_missing(tmp_path, monkeypatch):
    external, adapter = _prepare_external_recovery_test(tmp_path, monkeypatch)
    policy_path = tmp_path / "config" / "xmrig.policy.json"
    policy_path.unlink()

    def unexpected_start(_decision):
        raise AssertionError("Recovery must not launch without policy.")

    monkeypatch.setattr(adapter, "start", unexpected_start)
    result = adapter.recover({"test": True})

    assert result["status"] == "RESTART_BLOCKED"
    assert "policy" in result["reason"].lower()
    assert external.read_json(adapter.state_path, {})["pid"] == 45678
