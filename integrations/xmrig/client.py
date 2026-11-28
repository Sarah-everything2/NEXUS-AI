import json
import math
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MINER = Path(os.environ.get("NEXUS_XMRIG_DIR", str(ROOT / "miners" / "xmrig"))).expanduser().resolve()
EXE = MINER / "xmrig.exe"
BASE_CONFIG = MINER / "config.json"
RUNTIME_CONFIG = ROOT / "config" / "xmrig.runtime.json"
STATE = ROOT / "config" / "xmrig.state.json"
PROFILES = ROOT / "config" / "xmrig.profiles.json"
LOG = ROOT / "logs" / "xmrig.log"


def _read_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(temp, path)



def _inspect_process(pid):
    """Return RUNNING, EXITED, or UNKNOWN without conflating inspection errors."""
    if isinstance(pid, bool):
        return "UNKNOWN", None

    try:
        pid = int(pid)
    except (TypeError, ValueError, OverflowError):
        return "UNKNOWN", None

    if pid <= 0:
        return "UNKNOWN", None

    command = (
        "$ErrorActionPreference = 'Stop'; "
        f"$p = Get-CimInstance Win32_Process -Filter 'ProcessId={pid}' "
        "-ErrorAction Stop; "
        "if ($null -eq $p) { '__NEXUS_PROCESS_EXITED__' } "
        "elseif ([string]::IsNullOrWhiteSpace($p.ExecutablePath)) "
        "{ '__NEXUS_PROCESS_UNKNOWN__' } "
        "else { $p.ExecutablePath }"
    )

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return "UNKNOWN", None

    if result.returncode != 0:
        return "UNKNOWN", None

    output = (result.stdout or "").strip()
    if output == "__NEXUS_PROCESS_EXITED__":
        return "EXITED", None
    if not output or output == "__NEXUS_PROCESS_UNKNOWN__":
        return "UNKNOWN", None

    return "RUNNING", output


def _valid_saved_pid(value):
    return (
        not isinstance(value, bool)
        and isinstance(value, int)
        and value > 0
    )


def _same_executable(actual):
    if not isinstance(actual, str) or not actual.strip():
        return False
    return os.path.normcase(os.path.normpath(actual)) == os.path.normcase(
        os.path.normpath(str(EXE))
    )


def status():
    if not STATE.exists():
        return {
            "status": "STOPPED",
            "pid": None,
            "executable": str(EXE),
            "runtime_configured": RUNTIME_CONFIG.is_file(),
            "log": str(LOG),
        }

    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        state = None

    if not isinstance(state, dict) or not _valid_saved_pid(state.get("pid")):
        process_status, pid = "UNKNOWN", None
    else:
        pid = state["pid"]
        process_status, actual = _inspect_process(pid)

        if process_status == "RUNNING" and not _same_executable(actual):
            process_status = "UNKNOWN"
        elif process_status == "EXITED":
            process_status = "STOPPED"

        if process_status != "RUNNING":
            pid = None

    return {
        "status": process_status,
        "pid": pid,
        "executable": str(EXE),
        "runtime_configured": RUNTIME_CONFIG.is_file(),
        "log": str(LOG),
    }


def health():
    result = status()
    try:
        import ctypes
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)
            ]
        mem = MEMORYSTATUSEX()
        mem.dwLength = ctypes.sizeof(mem)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
        result["memory_used_percent"] = mem.dwMemoryLoad
        result["available_ram_gb"] = round(mem.ullAvailPhys / 1073741824, 2)
    except Exception as exc:
        result["memory_check"] = str(exc)
    return result



def configure_pools(coin, algorithm, pools, threads=25):
    """Configure one coin profile with multiple compatible failover pools."""
    if not isinstance(coin, str) or not coin.strip():
        raise ValueError("Coin name is required.")
    if not isinstance(algorithm, str) or not algorithm.strip():
        raise ValueError("XMRig algorithm is required.")
    if not isinstance(pools, list) or not pools:
        raise ValueError("At least one mining pool is required.")

    normalized = []
    for item in pools:
        if not isinstance(item, dict):
            raise ValueError("Each pool must be an object.")

        url = str(item.get("url", "")).strip()
        wallet = str(item.get("wallet", "")).strip()
        password = str(item.get("password", "x") or "x")
        tls = bool(item.get("tls", False))

        if not url or not wallet:
            raise ValueError("Every pool requires a URL and wallet.")
        if "://" in url or any(ch.isspace() for ch in url):
            raise ValueError("Pool URL must be hostname:port.")
        if "donate.v2.xmrig.com" in url.lower():
            raise ValueError("XMRig donation endpoint is not an allowed pool.")

        normalized.append({
            "url": url,
            "user": wallet,
            "pass": password,
            "keepalive": True,
            "tls": tls,
            "coin": coin.strip().lower(),
            "algo": algorithm.strip()
        })

    try:
        threads = int(threads)
    except (TypeError, ValueError):
        raise ValueError("Thread limit must be an integer.")
    if not 1 <= threads <= 100:
        raise ValueError("Thread limit must be between 1 and 100.")

    config = _read_json(BASE_CONFIG)
    if not config:
        raise RuntimeError("Original XMRig configuration could not be read.")

    config["pools"] = normalized
    config.setdefault("cpu", {})["enabled"] = True
    config["cpu"]["max-threads-hint"] = threads
    config["cpu"]["huge-pages"] = False

    _save_json(RUNTIME_CONFIG, config)

    profiles = _read_json(PROFILES, {})
    profiles[coin.strip().lower()] = {
        "coin": coin.strip().lower(),
        "algorithm": algorithm.strip(),
        "pool_count": len(normalized),
        "configured_at": time.time()
    }
    _save_json(PROFILES, profiles)

    return {
        "status": "CONFIGURED",
        "coin": coin.strip().lower(),
        "algorithm": algorithm.strip(),
        "pool_count": len(normalized),
        "failover_enabled": len(normalized) > 1,
        "cpu_thread_hint": threads,
        "original_config_preserved": True
    }


def configure_pool(url, wallet, algorithm, password="x", tls=False):
    return configure_pools(
        coin="custom",
        algorithm=algorithm,
        pools=[{
            "url": url,
            "wallet": wallet,
            "password": password,
            "tls": tls
        }]
    )


def list_coin_profiles():
    profiles = _read_json(PROFILES, {})
    active = _read_json(RUNTIME_CONFIG, {})
    active_pools = active.get("pools", [])
    return {
        "profiles": profiles,
        "active_coin": (
            active_pools[0].get("coin")
            if active_pools else None
        ),
        "configured_pool_count": len(active_pools)
    }



def _validate_profitability_decision(decision):
    """Require a fresh, finite, positive profitability approval."""
    if not isinstance(decision, dict):
        raise RuntimeError("Mining blocked: fresh profitability approval required.")

    if decision.get("status") != "RECOMMENDATION_READY":
        raise RuntimeError("Mining blocked: no profitable recommendation.")

    selected = decision.get("selected")
    if not isinstance(selected, dict):
        raise RuntimeError("Mining blocked: selected coin is missing.")

    coin = selected.get("coin")
    algorithm = selected.get("algorithm")
    if not isinstance(coin, str) or not coin.strip():
        raise RuntimeError("Mining blocked: approved coin is invalid.")
    if not isinstance(algorithm, str) or not algorithm.strip():
        raise RuntimeError("Mining blocked: approved algorithm is invalid.")

    raw_time = decision.get("evaluated_at")
    raw_profit = selected.get(
        "estimated_net_profit_per_day",
        selected.get("net_profit_per_day")
    )
    if isinstance(raw_time, bool) or isinstance(raw_profit, bool):
        raise RuntimeError("Mining blocked: invalid profitability decision.")

    try:
        evaluated_at = float(raw_time)
        net_profit = float(raw_profit)
    except (TypeError, ValueError, OverflowError):
        raise RuntimeError("Mining blocked: invalid profitability decision.")

    if not math.isfinite(evaluated_at) or not math.isfinite(net_profit):
        raise RuntimeError("Mining blocked: non-finite profitability data.")

    age = time.time() - evaluated_at
    if age < 0 or age > 120:
        raise RuntimeError("Mining blocked: profitability decision is stale.")

    if net_profit <= 0:
        raise RuntimeError("Mining blocked: net profitability is not positive.")

    return selected


def start(profitability_decision=None):
    from integrations.mining.process_lock import process_lock
    with process_lock(ROOT / "config" / "mining" / ".external-miners.lock"):
        return _start_locked(profitability_decision)


def _start_locked(profitability_decision=None):
    policy_path = ROOT / "config" / "xmrig.policy.json"
    emergency_stop = ROOT / "config" / "MINING_EMERGENCY_STOP"
    policy = _read_json(policy_path, {})

    if emergency_stop.exists():
        raise RuntimeError("Mining blocked: emergency stop is active.")

    if policy.get("mining_enabled") is not True:
        raise RuntimeError("Mining blocked: mining is not enabled.")

    if policy.get("autonomous_execution_enabled") is not True:
        raise RuntimeError("Mining blocked: autonomous execution is not enabled.")

    if policy.get("stop_when_unprofitable") is not True:
        raise RuntimeError("Mining blocked: profitability protection must remain enabled.")

    selected = _validate_profitability_decision(profitability_decision)

    memory = health()
    available_ram = memory.get("available_ram_gb")
    minimum_ram = policy.get("minimum_available_ram_gb", 1.5)

    if (isinstance(minimum_ram, bool)
            or not isinstance(minimum_ram, (int, float))
            or minimum_ram <= 0):
        raise RuntimeError("Mining blocked: invalid minimum RAM policy.")

    if (not isinstance(available_ram, (int, float))
            or available_ram < float(minimum_ram)):
        raise RuntimeError(
            f"Mining blocked: {available_ram} GB RAM available; "
            f"at least {minimum_ram} GB is required."
        )

    if not EXE.is_file():
        raise FileNotFoundError(f"XMRig executable not found: {EXE}")

    if not RUNTIME_CONFIG.is_file():
        raise RuntimeError("Configure a mining pool, wallet and algorithm first.")

    config = _read_json(RUNTIME_CONFIG)
    pools = config.get("pools", [])

    if not isinstance(pools, list) or not pools:
        raise RuntimeError("Mining pool configuration is missing.")

    pool = pools[0]
    if not isinstance(pool, dict) or not pool.get("user"):
        raise RuntimeError("Mining pool wallet is missing.")

    if "donate.v2.xmrig.com" in str(pool.get("url", "")).lower():
        raise RuntimeError("Donation endpoint blocked.")

    if str(pool.get("coin", "")).lower() != str(selected.get("coin", "")).lower():
        raise RuntimeError("Mining blocked: configured pool coin does not match the approved coin.")

    if str(pool.get("algo", "")).lower() != str(selected.get("algorithm", "")).lower():
        raise RuntimeError("Mining blocked: configured pool algorithm does not match the approved algorithm.")

    current = status()
    if current["status"] == "RUNNING":
        return {"status": "ALREADY_RUNNING", "pid": current["pid"]}
    if current["status"] != "STOPPED":
        raise RuntimeError(
            "Mining blocked: existing XMRig process ownership is uncertain."
        )

    from integrations.mining.process_lock import ensure_no_other_miner_running
    ensure_no_other_miner_running("xmrig")

    # Recheck the emergency stop immediately before process creation.
    if emergency_stop.exists():
        raise RuntimeError("Mining blocked: emergency stop became active.")

    LOG.parent.mkdir(parents=True, exist_ok=True)
    log_handle = open(LOG, "a", encoding="utf-8")

    try:
        process = subprocess.Popen(
            [str(EXE), "--config=" + str(RUNTIME_CONFIG)],
            cwd=str(MINER),
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    finally:
        log_handle.close()

    time.sleep(2)
    if process.poll() is not None:
        raise RuntimeError("XMRig exited during startup. Inspect mining logs.")

    _save_json(STATE, {"pid": process.pid, "started_at": time.time()})
    return {"status": "STARTED", "pid": process.pid}




def stop():
    from integrations.mining.process_lock import process_lock
    with process_lock(ROOT / "config" / "mining" / ".external-miners.lock"):
        return _stop_locked()


def _stop_locked():
    if not STATE.exists():
        return {"status": "NOT_RUNNING"}

    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {
            "status": "STOP_BLOCKED",
            "reason": "Saved process state is unreadable; state preserved.",
        }

    if not isinstance(state, dict) or not _valid_saved_pid(state.get("pid")):
        return {
            "status": "STOP_BLOCKED",
            "reason": "Saved PID is invalid; state preserved.",
        }

    pid = state["pid"]
    ownership, actual = _inspect_process(pid)

    if ownership == "EXITED":
        STATE.unlink(missing_ok=True)
        return {"status": "STOPPED", "pid": pid}

    if ownership != "RUNNING":
        return {
            "status": "STOP_BLOCKED",
            "reason": "Process state is unknown; saved state preserved.",
            "pid": pid,
        }

    if not _same_executable(actual):
        return {
            "status": "STOP_BLOCKED",
            "reason": "PID does not belong to configured XMRig; state preserved.",
            "pid": pid,
        }

    try:
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "status": "STOP_FAILED",
            "reason": str(exc),
            "pid": pid,
        }

    time.sleep(1)
    final_status, final_executable = _inspect_process(pid)

    if final_status == "EXITED":
        STATE.unlink(missing_ok=True)
        return {"status": "STOPPED", "pid": pid}

    reason = (
        "XMRig process remains running."
        if final_status == "RUNNING" and _same_executable(final_executable)
        else "Process exit could not be confirmed; saved state preserved."
    )
    if result.stderr.strip():
        reason += " " + result.stderr.strip()

    return {"status": "STOP_FAILED", "reason": reason, "pid": pid}


def logs(lines=30):
    if not LOG.is_file():
        return "No XMRig log exists yet."
    return "\n".join(LOG.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines()[-max(1, min(int(lines), 100)):])



def recovery_check(profitability_decision=None):
    from integrations.mining.process_lock import process_lock
    with process_lock(ROOT / "config" / "mining" / ".external-miners.lock"):
        return _recovery_check_locked(profitability_decision)


def _recovery_check_locked(profitability_decision=None):
    if not STATE.exists():
        return {"status": "IDLE", "crash_detected": False}

    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {
            "status": "RESTART_BLOCKED",
            "reason": "Saved XMRig process state is unreadable; recovery blocked.",
        }

    if not isinstance(state, dict) or not _valid_saved_pid(state.get("pid")):
        return {
            "status": "RESTART_BLOCKED",
            "reason": "Saved XMRig PID is invalid; recovery blocked.",
        }

    pid = state["pid"]
    ownership, actual = _inspect_process(pid)

    if ownership == "RUNNING":
        if _same_executable(actual):
            return {
                "status": "RUNNING",
                "crash_detected": False,
                "pid": pid,
            }
        return {
            "status": "RESTART_BLOCKED",
            "reason": "PID belongs to another executable; recovery blocked.",
        }

    if ownership != "EXITED":
        return {
            "status": "RESTART_BLOCKED",
            "reason": "Previous XMRig process state is unknown; recovery blocked.",
        }

    policy_path = ROOT / "config" / "xmrig.policy.json"
    emergency_stop = ROOT / "config" / "MINING_EMERGENCY_STOP"
    policy = _read_json(policy_path, {})

    memory = health()
    available = memory.get("available_ram_gb")
    now = time.time()

    history = _read_json(ROOT / "config" / "xmrig.recovery.json", {})
    if not isinstance(history, dict):
        return {"status": "RESTART_BLOCKED", "reason": "Invalid recovery history"}

    raw_attempts = history.get("attempts", [])
    if not isinstance(raw_attempts, list):
        return {"status": "RESTART_BLOCKED", "reason": "Invalid recovery attempt list"}

    attempts = []
    for item in raw_attempts:
        if not isinstance(item, dict):
            return {"status": "RESTART_BLOCKED", "reason": "Malformed recovery history entry"}
        try:
            timestamp = float(item["timestamp"])
        except (KeyError, TypeError, ValueError, OverflowError):
            return {"status": "RESTART_BLOCKED", "reason": "Invalid recovery timestamp"}

        if not math.isfinite(timestamp) or timestamp > now + 60:
            return {"status": "RESTART_BLOCKED", "reason": "Invalid recovery timestamp"}

        if 0 <= now - timestamp < 3600:
            attempts.append(item)

    event = {
        "event": "XMRIG_EXITED_UNEXPECTEDLY",
        "previous_pid": pid,
        "detected_at": now,
        "available_ram_gb": available,
        "automatic_restart": False
    }

    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write("\nRECOVERY EVENT: " + json.dumps(event) + "\n")

    if emergency_stop.exists():
        return {"status": "RESTART_BLOCKED", "reason": "Emergency stop active"}

    if policy.get("mining_enabled") is not True:
        return {"status": "CRASH_DETECTED", "restart_authorized": False,
                "reason": "Mining is not enabled in policy"}

    if policy.get("autonomous_restart_enabled") is not True:
        return {"status": "CRASH_DETECTED", "restart_authorized": False,
                "reason": "Autonomous restart is not enabled"}

    if policy.get("autonomous_execution_enabled") is not True:
        return {"status": "RESTART_BLOCKED",
                "reason": "Autonomous execution is not enabled"}

    if policy.get("stop_when_unprofitable") is not True:
        return {"status": "RESTART_BLOCKED",
                "reason": "Profitability protection must remain enabled"}

    try:
        _validate_profitability_decision(profitability_decision)
    except Exception as exc:
        return {
            "status": "RESTART_BLOCKED",
            "restart_authorized": False,
            "reason": str(exc)
        }

    maximum = policy.get("maximum_restarts_per_hour", 3)
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 0:
        return {"status": "RESTART_BLOCKED", "reason": "Invalid hourly restart limit"}

    if len(attempts) >= maximum:
        return {"status": "RESTART_BLOCKED", "reason": "Hourly restart limit reached"}

    minimum_ram = policy.get("minimum_available_ram_gb", 1.5)
    if (
        isinstance(minimum_ram, bool)
        or not isinstance(minimum_ram, (int, float))
        or not math.isfinite(minimum_ram)
        or minimum_ram <= 0
    ):
        return {"status": "RESTART_BLOCKED", "reason": "Invalid minimum RAM policy"}

    if (
        isinstance(available, bool)
        or not isinstance(available, (int, float))
        or not math.isfinite(available)
        or available < minimum_ram
    ):
        return {"status": "RESTART_BLOCKED", "reason": "Insufficient or invalid available RAM"}

    if not EXE.is_file() or not RUNTIME_CONFIG.is_file():
        return {"status": "RESTART_BLOCKED", "reason": "Miner or runtime configuration missing"}

    attempts.append({"timestamp": now, "previous_pid": pid})
    _save_json(ROOT / "config" / "xmrig.recovery.json", {"attempts": attempts})

    try:
        result = start(profitability_decision=profitability_decision)
        return {
            "status": "RESTARTED" if result.get("status") == "STARTED" else result.get("status"),
            "crash_detected": True,
            "restart_authorized": True,
            "restart": result
        }
    except Exception as exc:
        return {
            "status": "RESTART_FAILED",
            "crash_detected": True,
            "reason": str(exc)
        }
