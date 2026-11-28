import json
from pathlib import Path

import pytest

from integrations.xmrig import client


def write_state(tmp_path, payload):
    state = tmp_path / "xmrig.state.json"
    state.write_text(json.dumps(payload), encoding="utf-8")
    return state


def test_status_reports_stopped_only_when_state_file_is_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(client, "STATE", tmp_path / "missing.json")
    result = client.status()
    assert result["status"] == "STOPPED"


def test_status_reports_unknown_for_malformed_saved_state(tmp_path, monkeypatch):
    state = tmp_path / "xmrig.state.json"
    state.write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(client, "STATE", state)

    result = client.status()
    assert result["status"] == "UNKNOWN"


@pytest.mark.parametrize("pid", [0, -1, True, "invalid", None])
def test_status_reports_unknown_for_invalid_saved_pid(tmp_path, monkeypatch, pid):
    monkeypatch.setattr(client, "STATE", write_state(tmp_path, {"pid": pid}))
    assert client.status()["status"] == "UNKNOWN"


def test_status_distinguishes_confirmed_exit_from_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(client, "STATE", write_state(tmp_path, {"pid": 1234}))
    monkeypatch.setattr(client, "_inspect_process", lambda pid: ("EXITED", None))
    assert client.status()["status"] == "STOPPED"

    monkeypatch.setattr(client, "_inspect_process", lambda pid: ("UNKNOWN", None))
    assert client.status()["status"] == "UNKNOWN"


def test_status_requires_verified_xmrig_executable(tmp_path, monkeypatch):
    monkeypatch.setattr(client, "STATE", write_state(tmp_path, {"pid": 1234}))
    monkeypatch.setattr(
        client, "_inspect_process",
        lambda pid: ("RUNNING", str(client.EXE))
    )
    assert client.status()["status"] == "RUNNING"

    monkeypatch.setattr(
        client, "_inspect_process",
        lambda pid: ("RUNNING", "C:\\Windows\\System32\\not-xmrig.exe")
    )
    assert client.status()["status"] == "UNKNOWN"


def test_stop_preserves_state_when_process_inspection_is_unknown(tmp_path, monkeypatch):
    state = write_state(tmp_path, {"pid": 1234})
    monkeypatch.setattr(client, "STATE", state)
    monkeypatch.setattr(client, "_inspect_process", lambda pid: ("UNKNOWN", None))

    result = client.stop()

    assert result["status"] == "STOP_BLOCKED"
    assert state.exists()


def test_stop_clears_state_only_after_confirmed_exit(tmp_path, monkeypatch):
    state = write_state(tmp_path, {"pid": 1234})
    monkeypatch.setattr(client, "STATE", state)
    monkeypatch.setattr(client, "_inspect_process", lambda pid: ("EXITED", None))

    result = client.stop()

    assert result["status"] == "STOPPED"
    assert not state.exists()


def test_recovery_blocks_when_previous_process_is_unknown(tmp_path, monkeypatch):
    state = write_state(tmp_path, {"pid": 1234})
    monkeypatch.setattr(client, "STATE", state)
    monkeypatch.setattr(client, "_inspect_process", lambda pid: ("UNKNOWN", None))

    result = client.recovery_check()

    assert result["status"] == "RESTART_BLOCKED"
    assert state.exists()
