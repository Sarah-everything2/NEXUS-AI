"""NEXUS AI: controlled Headway-Demo daily MT5 session manager."""
import json
import os
import subprocess
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
BRIDGE = Path(r"C:\AI-Trading\mt5-bridge")
PYTHON = BRIDGE / ".venv" / "Scripts" / "python.exe"
CONFIG = BRIDGE / "config" / "trading_safety.json"
DATA = PROJECT / "data"
LOGS = PROJECT / "logs"
STATE = DATA / "mt5_daily_session.json"
BRIDGE_URL = "http://127.0.0.1:8001/"
BRIDGE_LOG = LOGS / "mt5_bridge.log"

MONITOR_STOP = BRIDGE / "strategy" / "signal_monitor.stop"
WORKER_STOP = BRIDGE / "strategy" / "auto_demo_worker.stop"
EMERGENCY_STOP = BRIDGE / "strategy" / "emergency_stop.flag"

MONITOR_MODULE = "strategy.signal_monitor"
WORKER_MODULE = "strategy.auto_demo_worker"

_processes = {}
_bridge_process = None


def _load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def _save_state(state):
    DATA.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _load_safety():
    if not CONFIG.is_file():
        raise RuntimeError(f"Trading safety config missing: {CONFIG}")
    config = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    if not os.environ.get("MT5_EXPECTED_LOGIN", "").strip():
        raise RuntimeError("MT5_EXPECTED_LOGIN is not configured")
    required = {
        "demo_only": True,
        "execution_enabled": True,
        "demo_execution_enabled": True,
        "live_execution_enabled": False,
        "automatic_demo_trading_enabled": True,
        "require_stop_loss": True,
        "require_take_profit": True,
    }
    for key, expected in required.items():
        if config.get(key) is not expected:
            raise RuntimeError(f"Safety check failed: {key} must be {expected}")
    if float(config.get("maximum_volume", 0)) > 0.01:
        raise RuntimeError("Maximum volume exceeds 0.01")
    if int(config.get("maximum_open_positions", 0)) > 1:
        raise RuntimeError("Maximum open positions exceeds 1")
    if float(config.get("maximum_risk_percent", 0)) > 1:
        raise RuntimeError("Maximum risk exceeds 1 percent")
    if int(config.get("maximum_quote_age_seconds", 0)) > 300:
        raise RuntimeError("Quote age limit exceeds 300 seconds")
    return config


def show_plan():
    today = datetime.now().strftime("%Y-%m-%d")
    state = _load_state()
    if state.get("date") != today:
        state = {
            "date": today,
            "selected": ["trading"],
            "approved": False,
            "status": "PLANNED",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        _save_state(state)

    print("\n=== NEXUS AI DAILY MT5 PLAN ===")
    print("Date:", state["date"])
    print("Activity: Headway-Demo automatic trading")
    print("Account restriction: DEMO ONLY")
    print("Per-trade human approval: NOT REQUIRED")
    print("Daily human approval: NOT REQUIRED")
    print("Session status:", state.get("status", "PLANNED"))
    print("Live-account execution: BLOCKED")
    print("Autonomous session authorization: CONFIGURED")
    return state


def _pid_running(pid):
    if not pid:
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {int(pid)}", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
        return str(pid) in result.stdout
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


def bridge_healthy():
    try:
        with urllib.request.urlopen(BRIDGE_URL, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return response.status == 200 and payload.get("status") == "online"
    except Exception:
        return False



def bridge_listener_pid():
    """Return the PID listening on the bridge port, if any."""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command",
         "Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    pids = {int(x) for x in result.stdout.split() if x.isdigit()}
    if len(pids) > 1:
        raise RuntimeError("Multiple processes reported on bridge port 8001.")
    return next(iter(pids), None)


def bridge_process_matches(pid):
    """Verify the exact existing MT5 bridge command before stopping it."""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command",
         f"Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}' | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return False
    try:
        process = json.loads(result.stdout)
        command = (process.get("CommandLine") or "").lower()
        return (
            str(BRIDGE).lower() in command
            and "mt5_api:app" in command
            and "--port 8001" in command
            and "uvicorn" in command
        )
    except (ValueError, AttributeError):
        return False


def _stop_verified_bridge(pid):
    if not bridge_process_matches(pid):
        raise RuntimeError(
            f"Safety stop: PID {pid} does not match the verified MT5 bridge. Nothing stopped."
        )
    subprocess.run(
        ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
        capture_output=True, text=True, timeout=15, check=True,
    )
    for _ in range(10):
        if bridge_listener_pid() != pid:
            return True
        time.sleep(1)
    raise RuntimeError(f"Verified bridge PID {pid} did not stop.")


def start_bridge_server():
    """Start or reuse the API only. Never starts trading workers."""
    global _bridge_process
    state = _load_state()

    if bridge_healthy():
        pid = bridge_listener_pid()
        state.update({"bridge_status": "ONLINE", "bridge_pid": pid})
        _save_state(state)
        print(f"MT5 API already healthy. Reusing PID {pid}.")
        return True

    pid = bridge_listener_pid()
    if pid is not None:
        if not bridge_process_matches(pid):
            raise RuntimeError(
                f"Port 8001 is occupied by unverified PID {pid}; refusing to stop it."
            )
        print(f"Found unresponsive verified bridge PID {pid}; restarting API only.")
        _stop_verified_bridge(pid)

    if not PYTHON.is_file():
        raise RuntimeError(f"Bridge Python not found: {PYTHON}")

    LOGS.mkdir(parents=True, exist_ok=True)
    with BRIDGE_LOG.open("a", encoding="utf-8") as handle:
        _bridge_process = subprocess.Popen(
            [str(PYTHON), "-u", "-m", "uvicorn", "mt5_api:app",
             "--host", "127.0.0.1", "--port", "8001"],
            cwd=str(BRIDGE), stdin=subprocess.DEVNULL,
            stdout=handle, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )

    for _ in range(20):
        if _bridge_process.poll() is not None:
            raise RuntimeError(f"Bridge exited during startup. Check {BRIDGE_LOG}")
        if bridge_healthy():
            pid = bridge_listener_pid()
            state.update({
                "bridge_status": "ONLINE",
                "bridge_owned": True,
                "bridge_pid": pid,
                "bridge_started_at": datetime.now().isoformat(timespec="seconds"),
            })
            _save_state(state)
            print(f"PASS: MT5 API online. PID {pid}. Trading workers were not started.")
            return True
        time.sleep(1)

    _bridge_process.terminate()
    raise RuntimeError(f"Bridge health check timed out. Check {BRIDGE_LOG}")


def bridge_server_status():
    pid = bridge_listener_pid()
    healthy = bridge_healthy()
    print("\n=== MT5 API SERVER STATUS ===")
    print("API:", "ONLINE" if healthy else "OFFLINE / UNRESPONSIVE")
    print("Port:", "8001")
    print("Listener PID:", pid if pid else "None")
    if pid:
        print("Verified bridge process:", "YES" if bridge_process_matches(pid) else "NO")
    state = _load_state()
    print("Trading monitor:", "RUNNING" if _pid_running(state.get("monitor_pid")) else "NOT RUNNING")
    print("Trading worker:", "RUNNING" if _pid_running(state.get("worker_pid")) else "NOT RUNNING")
    return healthy


def restart_bridge_server():
    pid = bridge_listener_pid()
    if pid is not None:
        _stop_verified_bridge(pid)
    print("Verified MT5 API stopped. Starting API server only...")
    return start_bridge_server()


def stop_bridge_server():
    pid = bridge_listener_pid()
    if pid is None:
        print("MT5 API server is already stopped.")
        return True
    _stop_verified_bridge(pid)
    state = _load_state()
    state.update({"bridge_status": "OFFLINE"})
    state.pop("bridge_pid", None)
    state.pop("bridge_owned", None)
    _save_state(state)
    print("PASS: Verified MT5 API server stopped. Trading workers were not changed.")
    return True


def ensure_bridge():
    """Trading-session bridge prerequisite; API startup remains separate."""
    return start_bridge_server()


def status():
    state = _load_state()
    print("\n=== MT5 SESSION STATUS ===")
    print("Date:", state.get("date", "No plan created"))
    print("Approval:", "APPROVED" if state.get("approved") else "PENDING")
    print("State:", state.get("status", "STOPPED"))
    print("MT5 Bridge:", "ONLINE" if bridge_healthy() else "OFFLINE")
    for name in ("monitor", "worker"):
        pid = state.get(f"{name}_pid")
        running = _pid_running(pid)
        print(f"{name.title()}:",
              f"PID {pid} RUNNING" if running else "NOT RUNNING")
    return state


def start_session(daily_approval=False):
    today = datetime.now().strftime("%Y-%m-%d")
    state = _load_state()

    if EMERGENCY_STOP.exists():
        raise RuntimeError("EMERGENCY STOP ACTIVE. Manual clearance is required before restarting.")

    if state.get("date") != today:
        state.update({
            "date": today,
            "selected": ["trading"],
            "approved": False,
            "status": "PLANNED",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        })
        _save_state(state)
    if "trading" not in state.get("selected", []):
        raise RuntimeError("Trading is not selected in today's plan.")

    _load_safety()

    ensure_bridge()

    if not PYTHON.is_file():
        raise RuntimeError(f"Bridge Python not found: {PYTHON}")
    for module in (MONITOR_MODULE, WORKER_MODULE):
        module_file = BRIDGE / (module.replace(".", "\\") + ".py")
        if not module_file.is_file():
            raise RuntimeError(f"Required module missing: {module_file}")

    for name in ("monitor", "worker"):
        if _pid_running(state.get(f"{name}_pid")):
            raise RuntimeError(f"{name.title()} already appears to be running.")

    LOGS.mkdir(parents=True, exist_ok=True)
    MONITOR_STOP.unlink(missing_ok=True)
    WORKER_STOP.unlink(missing_ok=True)

    state.update({
        "approved": True,
        "approved_at": datetime.now().isoformat(timespec="seconds"),
        "status": "STARTING",
    })
    _save_state(state)

    launched = {}
    try:
        for name, module in (
            ("monitor", MONITOR_MODULE),
            ("worker", WORKER_MODULE),
        ):
            log_path = LOGS / f"mt5_{name}.log"
            log_handle = log_path.open("a", encoding="utf-8")
            try:
                proc = subprocess.Popen(
                    [str(PYTHON), "-m", module],
                    cwd=str(BRIDGE),
                    stdin=subprocess.DEVNULL,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                )
            finally:
                log_handle.close()
            launched[name] = proc
            time.sleep(1)
            if proc.poll() is not None:
                raise RuntimeError(
                    f"{name.title()} exited during startup. Check {log_path}"
                )
    except Exception:
        MONITOR_STOP.touch()
        WORKER_STOP.touch()
        for proc in launched.values():
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        state.update({
            "approved": False,
            "status": "START FAILED",
            "startup_error_at": datetime.now().isoformat(timespec="seconds"),
        })
        _save_state(state)
        raise

    _processes.update(launched)
    state.update({
        "approved": True,
        "approved_at": datetime.now().isoformat(timespec="seconds"),
        "status": "RUNNING",
        "monitor_pid": launched["monitor"].pid,
        "worker_pid": launched["worker"].pid,
        "started_at": datetime.now().isoformat(timespec="seconds"),
    })
    _save_state(state)
    print("Session processes launched. Check /trading-status and worker logs.")
    print("The worker must independently verify the Headway-Demo account.")
    return state


def stop_owned_bridge(state):
    global _bridge_process
    if state.get("bridge_owned") is not True:
        print("Shared MT5 bridge preserved.")
        return True

    if _bridge_process is None or _bridge_process.poll() is not None:
        print("Owned bridge process handle unavailable; bridge left running safely.")
        return False

    try:
        _bridge_process.terminate()
        _bridge_process.wait(timeout=10)
        state["bridge_owned"] = False
        state["bridge_status"] = "OFFLINE"
        state.pop("bridge_pid", None)
        _save_state(state)
        print("PASS: NEXUS-owned MT5 bridge stopped.")
        _bridge_process = None
        return True
    except Exception as exc:
        print("WARNING: Could not stop owned bridge:", repr(exc))
        return False





def audit_emergency_event(event, state):
    LOGS.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "event": event,
        "session_date": state.get("date"),
        "approval": state.get("approved", False),
        "status": state.get("status"),
        "bridge_owned": state.get("bridge_owned", False),
    }
    with (LOGS / "mt5_emergency_audit.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def emergency_stop():
    state = _load_state()
    EMERGENCY_STOP.touch()
    MONITOR_STOP.touch()
    WORKER_STOP.touch()
    state.update({
        "approved": False,
        "status": "EMERGENCY STOP",
        "emergency_stop_at": datetime.now().isoformat(timespec="seconds"),
    })
    _save_state(state)
    audit_emergency_event("EMERGENCY_STOP_ACTIVATED", state)
    print("EMERGENCY STOP ACTIVE: Approval revoked; trading processes signalled to stop.")
    return state

def clear_emergency_stop():
    state = _load_state()

    running = [
        name for name in ("monitor", "worker")
        if _pid_running(state.get(f"{name}_pid"))
    ]
    if running:
        raise RuntimeError(
            "Cannot clear emergency stop; processes still running: "
            + ", ".join(running)
        )

    if not EMERGENCY_STOP.exists():
        print("Emergency stop is already clear.")
        return state

    EMERGENCY_STOP.unlink()
    state.update({
        "approved": False,
        "status": "EMERGENCY STOP CLEARED - APPROVAL REQUIRED",
        "emergency_stop_cleared_at": datetime.now().isoformat(timespec="seconds"),
    })
    _save_state(state)
    audit_emergency_event("EMERGENCY_STOP_CLEARED", state)
    print("PASS: Emergency stop cleared. A new daily approval is still required.")
    return state


def stop_session():
    state = _load_state()
    MONITOR_STOP.touch()
    WORKER_STOP.touch()
    state["approved"] = False
    state["status"] = "STOP REQUESTED"
    state["stop_requested_at"] = datetime.now().isoformat(timespec="seconds")
    _save_state(state)

    print("Stop requested. Waiting for monitor and worker...")
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        running = [
            name for name in ("monitor", "worker")
            if _pid_running(state.get(f"{name}_pid"))
        ]
        if not running:
            bridge_stopped = stop_owned_bridge(state)
            state["status"] = (
                "STOPPED" if bridge_stopped
                else "STOPPED - BRIDGE STILL RUNNING"
            )
            state["stopped_at"] = datetime.now().isoformat(timespec="seconds")
            _save_state(state)
            print("PASS: Monitor and worker exited. Daily approval revoked.")
            return state
        time.sleep(1)

    state["status"] = "STOP TIMEOUT"
    _save_state(state)
    print("WARNING: Still running:", ", ".join(running))
    print("Daily approval remains revoked; worker order-submission guard remains active.")
    return state
