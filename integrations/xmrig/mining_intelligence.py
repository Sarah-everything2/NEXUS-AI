"""Central intelligence cycle using configured market providers."""

import json
import time
from pathlib import Path

from integrations.xmrig import market_feed, hardware_monitor

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "config" / "xmrig.policy.json"


def _read_policy():
    try:
        data = json.loads(POLICY.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def collect_opportunities():
    report = {
        "timestamp": time.time(),
        "status": "INCOMPLETE",
        "opportunities": [],
        "errors": [],
    }

    try:
        refreshed = market_feed.refresh()
        opportunities = market_feed.get_opportunities()

        if not opportunities:
            report["errors"].append(
                "market: no fresh configured provider opportunities"
            )
            report["market"] = refreshed
            return report

        report["market"] = refreshed
    except Exception as exc:
        report["errors"].append("market:" + type(exc).__name__)
        return report

    try:
        hardware = hardware_monitor.collect()
        if not hardware.get("telemetry_complete"):
            report["errors"].append("hardware: incomplete hardware telemetry")
            report["hardware"] = hardware
            return report
    except Exception as exc:
        report["errors"].append("hardware:" + type(exc).__name__)
        return report

    report["opportunities"] = opportunities
    report["hardware"] = hardware
    report["status"] = "READY"
    return report


def run_cycle(electricity_price_per_kwh=None):
    from integrations.xmrig.autopilot import run_cycle as run_autopilot

    policy = _read_policy()
    if electricity_price_per_kwh is None:
        electricity_price_per_kwh = policy.get("electricity_price_per_kwh")

    if (isinstance(electricity_price_per_kwh, bool)
            or not isinstance(electricity_price_per_kwh, (int, float))
            or electricity_price_per_kwh < 0):
        return {
            "status": "BLOCKED",
            "reason": "A valid electricity price must be configured.",
            "execution_authorized": False,
        }

    intelligence = collect_opportunities()
    if intelligence["status"] != "READY":
        return {
            "status": "BLOCKED",
            "intelligence": intelligence,
            "execution_authorized": False,
        }

    result = run_autopilot(
        opportunities=intelligence["opportunities"],
        electricity_price_per_kwh=electricity_price_per_kwh,
        hardware=intelligence["hardware"],
    )

    return {
        "status": result.get("status", "COMPLETED"),
        "intelligence": intelligence,
        "autopilot": result,
    }
