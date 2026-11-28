"""Read-only XMRig performance telemetry."""

import json
import os
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "config" / "xmrig.performance.json"
API = os.environ.get("NEXUS_XMRIG_API_URL", "http://127.0.0.1:18088/2/summary")


def collect():
    request = urllib.request.Request(
        API,
        headers={"Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        raw = response.read(256001)

    if len(raw) > 256000:
        raise RuntimeError("XMRig API response too large")

    data = json.loads(raw.decode("utf-8"))
    results = data.get("results", {})
    hashrate = results.get("hashrate", {})
    shares = results.get("shares", {})

    def rate(values):
        if isinstance(values, list) and values:
            return float(values[0] or 0)
        return 0.0

    snapshot = {
        "timestamp": time.time(),
        "hashrate_10s": rate(hashrate.get("total", [])),
        "accepted_shares": int(shares.get("accepted", 0)),
        "rejected_shares": int(shares.get("rejected", 0)),
        "total_shares": int(shares.get("total", 0)),
        "uptime_seconds": int(data.get("connection", {}).get("uptime", 0)),
        "source": "local_xmrig_api",
        "telemetry_type": "measured"
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temp = OUTPUT.with_suffix(".tmp")
    temp.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    temp.replace(OUTPUT)
    return snapshot


def get_performance(max_age_seconds=120):
    try:
        data = json.loads(OUTPUT.read_text(encoding="utf-8"))
        if time.time() - float(data["timestamp"]) > max_age_seconds:
            return None
        return data
    except (OSError, ValueError, KeyError, TypeError):
        return None
