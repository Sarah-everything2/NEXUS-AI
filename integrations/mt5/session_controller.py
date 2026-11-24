"""NEXUS AI: controlled Headway-Demo daily MT5 session manager."""
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
BRIDGE = Path(r"C:\AI-Trading\mt5-bridge")
PYTHON = BRIDGE / ".venv" / "Scripts" / "python.exe"
CONFIG = BRIDGE / "config" / "trading_safety.json"
DATA = PROJECT / "data"
LOGS = PROJECT / "logs"
STATE = DATA / "mt5_daily_session.json"

MONITOR_STOP = BRIDGE / "strategy" / "signal_monitor.stop"
WORKER_STOP = BRIDGE / "strategy" / "auto_demo_worker.stop"

MONITOR_MODULE = "strategy.signal_monitor"
WORKER_MODULE = "strategy.auto_demo_worker"

_processes = {}


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
    print("Daily approval:", "APPROVED" if state.get("approved") else "PENDING")
    print("Session status:", state.get("status", "PLANNED"))
    print("Live-account execution: BLOCKED")
    print("Type /trading-go and confirm GO to approve today's session.")
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


def status():
    state = _load_state()
    print("\n=== MT5 SESSION STATUS ===")
    print("Date:", state.get("date", "No plan created"))
    print("Approval:", "APPROVED" if state.get("approved") else "PENDING")
    print("State:", state.get("status", "STOPPED"))
    for name in ("monitor", "worker"):
        pid = state.get(f"{name}_pid")
        running = _pid_running(pid)
        print(f"{name.title()}:",
              f"PID {pid} RUNNING" if running else "NOT RUNNING")
    return state


def start_session(daily_approval=False):
    today = datetime.now().strftime("%Y-%m-%d")
    state = _load_state()

    if state.get("date") != today:
        raise RuntimeError("No current daily plan. Run /trading-plan first.")
    if not daily_approval:
        raise RuntimeError("Daily approval is required before starting.")
    if "trading" not in state.get("selected", []):
        raise RuntimeError("Trading is not selected in today's plan.")

    _load_safety()

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
        raise

    _processes.update(launched)
    state.update({
        "approved": True,
        "approved_at": datetime.now().isoformat(timespec="seconds"),
        "status": "STARTING",
        "monitor_pid": launched["monitor"].pid,
        "worker_pid": launched["worker"].pid,
        "started_at": datetime.now().isoformat(timespec="seconds"),
    })
    _save_state(state)
    print("Session processes launched. Check /trading-status and worker logs.")
    print("The worker must independently verify the Headway-Demo account.")
    return state


def stop_session():
    state = _load_state()
    MONITOR_STOP.touch()
    WORKER_STOP.touch()
    state["status"] = "STOP REQUESTED"
    state["stop_requested_at"] = datetime.now().isoformat(timespec="seconds")
    _save_state(state)

    print("Graceful stop requested for monitor and worker.")
    print("They check stop files on their normal polling intervals.")
    print("Use /trading-status to verify both processes have exited.")
    return state

