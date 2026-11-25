"""Resource telemetry for NEXUS mining decisions. No miner control."""

import json
import os
import subprocess
import time
import ctypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "config" / "xmrig.policy.json"
SNAPSHOT = ROOT / "config" / "xmrig.hardware.json"


def _memory():
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

    value = MEMORYSTATUSEX()
    value.dwLength = ctypes.sizeof(value)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
        raise RuntimeError("Windows memory telemetry unavailable")
    return round(value.ullAvailPhys / 1073741824, 2)


def _cpu_percent():
    try:
        import psutil
        return float(psutil.cpu_percent(interval=1))
    except ImportError:
        command = (
            "(Get-Counter '\\Processor(_Total)\\% Processor Time')."
            "CounterSamples[0].CookedValue"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True, text=True, timeout=8
        )
        if result.returncode != 0:
            raise RuntimeError("CPU telemetry unavailable")
        return round(float(result.stdout.strip()), 1)


def _temperature():
    command = (
        "Get-CimInstance -Namespace root/wmi "
        "-ClassName MSAcpi_ThermalZoneTemperature "
        "-ErrorAction Stop | "
        "Select-Object -First 1 -ExpandProperty CurrentTemperature"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True, text=True, timeout=8
        )
        raw = result.stdout.strip()
        if result.returncode != 0 or not raw:
            return None
        return round((float(raw) / 10.0) - 273.15, 1)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def collect():
    try:
        available_ram = _memory()
        cpu = _cpu_percent()
        temperature = _temperature()

        try:
            policy = json.loads(POLICY.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            policy = {}

        watts = policy.get("estimated_power_watts")
        if not isinstance(watts, (int, float)) or watts <= 0:
            watts = None

        data = {
            "timestamp": time.time(),
            "available_ram_gb": available_ram,
            "cpu_percent": cpu,
            "temperature_c": temperature,
            "estimated_power_watts": watts,
            "telemetry_complete": temperature is not None and watts is not None
        }

        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        temp_file = SNAPSHOT.with_suffix(".tmp")
        temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(temp_file, SNAPSHOT)
        return data

    except Exception as exc:
        return {
            "telemetry_complete": False,
            "status": "UNAVAILABLE",
            "reason": type(exc).__name__
        }
