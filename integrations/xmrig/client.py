import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MINER = Path(r"C:\Mininglab\miners\xmrig-6.26.0-windows-x64\xmrig-6.26.0")
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


def _process_executable(pid):
    try:
        pid = int(pid)
        if pid <= 0:
            return None
        command = (
            f"$p = Get-CimInstance Win32_Process "
            f"-Filter 'ProcessId={pid}'; "
            "if ($p) { $p.ExecutablePath }"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() or None
    except (ValueError, OSError, subprocess.TimeoutExpired):
        return None


def status():
    state = _read_json(STATE)
    pid = state.get("pid")
    actual = _process_executable(pid) if pid else None
    running = bool(
        actual and os.path.normcase(actual) == os.path.normcase(str(EXE))
    )

    return {
        "status": "RUNNING" if running else "STOPPED",
        "pid": int(pid) if running else None,
        "executable": str(EXE),
        "runtime_configured": RUNTIME_CONFIG.is_file(),
        "log": str(LOG)
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


def configure_pool(url, wallet, password="x", tls=False):
    return configure_pools(
        coin="custom",
        algorithm="",
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


def start():
    memory = health()
    available_ram = memory.get("available_ram_gb")

    if not isinstance(available_ram, (int, float)) or available_ram < 2.5:
        raise RuntimeError(
            f"Mining blocked: {available_ram} GB RAM available; "
            "at least 2.5 GB is required. Free memory or upgrade RAM first."
        )
    if not EXE.is_file():
        raise FileNotFoundError("XMRig executable not found.")
    if not RUNTIME_CONFIG.is_file():
        raise RuntimeError("Configure your own mining pool and wallet first.")

    config = _read_json(RUNTIME_CONFIG)
    pools = config.get("pools", [])
    if not pools or not pools[0].get("user"):
        raise RuntimeError("Mining pool or wallet is missing.")
    if "donate.v2.xmrig.com" in pools[0].get("url", "").lower():
        raise RuntimeError("Donation endpoint blocked.")

    current = status()
    if current["status"] == "RUNNING":
        return {"status": "ALREADY_RUNNING", "pid": current["pid"]}

    LOG.parent.mkdir(parents=True, exist_ok=True)
    log_handle = open(LOG, "a", encoding="utf-8")

    try:
        process = subprocess.Popen(
            [str(EXE), "--config=" + str(RUNTIME_CONFIG)],
            cwd=str(MINER),
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    finally:
        log_handle.close()

    time.sleep(2)
    if process.poll() is not None:
        raise RuntimeError("XMRig exited during startup. Inspect mining logs.")

    _save_json(STATE, {"pid": process.pid, "started_at": time.time()})
    return {"status": "STARTED", "pid": process.pid}


def stop():
    state = _read_json(STATE)
    pid = state.get("pid")

    if not pid:
        return {"status": "NOT_RUNNING"}

    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return {"status": "STOP_FAILED", "reason": "Invalid saved PID."}

    actual = _process_executable(pid)

    if not actual:
        STATE.unlink(missing_ok=True)
        return {"status": "NOT_RUNNING"}

    if os.path.normcase(actual) != os.path.normcase(str(EXE)):
        return {
            "status": "STOP_FAILED",
            "reason": "PID does not belong to the configured XMRig executable. State preserved."
        }

    result = subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True, text=True, timeout=15
    )

    time.sleep(1)
    remaining = _process_executable(pid)

    if remaining and os.path.normcase(remaining) == os.path.normcase(str(EXE)):
        return {
            "status": "STOP_FAILED",
            "reason": result.stderr.strip() or "XMRig process is still running.",
            "pid": pid
        }

    STATE.unlink(missing_ok=True)
    return {"status": "STOPPED", "pid": pid}


def logs(lines=30):
    if not LOG.is_file():
        return "No XMRig log exists yet."
    return "\n".join(LOG.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines()[-max(1, min(int(lines), 100)):])



def recovery_check():
    state = _read_json(STATE)
    pid = state.get("pid")

    if not pid:
        return {"status": "IDLE", "crash_detected": False}

    actual = _process_executable(pid)
    if actual and os.path.normcase(actual) == os.path.normcase(str(EXE)):
        return {"status": "RUNNING", "crash_detected": False, "pid": int(pid)}

    STATE.unlink(missing_ok=True)

    policy_path = ROOT / "config" / "xmrig.policy.json"
    emergency_stop = ROOT / "config" / "MINING_EMERGENCY_STOP"
    policy = _read_json(policy_path, {})

    memory = health()
    available = memory.get("available_ram_gb")
    now = time.time()

    history = _read_json(ROOT / "config" / "xmrig.recovery.json", {})
    attempts = [
        x for x in history.get("attempts", [])
        if now - float(x.get("timestamp", 0)) < 3600
    ]

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

    if len(attempts) >= int(policy.get("maximum_restarts_per_hour", 3)):
        return {"status": "RESTART_BLOCKED", "reason": "Hourly restart limit reached"}

    if not isinstance(available, (int, float)) or available < float(
        policy.get("minimum_available_ram_gb", 2.5)
    ):
        return {"status": "RESTART_BLOCKED", "reason": "Insufficient available RAM"}

    if not EXE.is_file() or not RUNTIME_CONFIG.is_file():
        return {"status": "RESTART_BLOCKED", "reason": "Miner or runtime configuration missing"}

    attempts.append({"timestamp": now, "previous_pid": pid})
    _save_json(ROOT / "config" / "xmrig.recovery.json", {"attempts": attempts})

    try:
        result = start()
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
