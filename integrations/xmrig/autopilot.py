"""NEXUS autonomous mining decision and execution coordinator."""

import json
import time
from pathlib import Path

from integrations.xmrig import client
from integrations.xmrig.coin_selector import evaluate_opportunities

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "config" / "xmrig.policy.json"
EMERGENCY = ROOT / "config" / "MINING_EMERGENCY_STOP"
AUDIT = ROOT / "logs" / "mining_autopilot.jsonl"


def _read(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


def _audit(event):
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": time.time(), **event}) + "\n")


def run_cycle(opportunities, electricity_price_per_kwh, hardware):
    """Evaluate mining. Execution occurs only when policy explicitly permits it."""
    policy = _read(POLICY)

    if EMERGENCY.exists():
        result = {"status": "EMERGENCY_STOP"}
        _audit(result)
        return result

    if policy.get("mining_enabled") is not True:
        return {"status": "DISABLED", "execution": False}

    decision = evaluate_opportunities(
        opportunities,
        electricity_price_per_kwh,
        hardware,
        settings=policy.get("profitability_limits", {})
    )

    if decision.get("status") != "RECOMMENDATION_READY":
        if policy.get("stop_when_unprofitable") is True:
            current = client.status()
            if current["status"] == "RUNNING":
                stopped = client.stop()
                result = {"status": "STOPPED_UNPROFITABLE", "stop": stopped,
                          "decision": decision}
                _audit(result)
                return result
        return {"status": decision.get("status"), "decision": decision,
                "execution": False}

    if policy.get("autonomous_execution_enabled") is not True:
        return {"status": "RECOMMENDATION_ONLY", "decision": decision,
                "execution": False}

    if EMERGENCY.exists():
        return {"status": "EMERGENCY_STOP", "execution": False}

    current = client.status()
    if current["status"] == "RUNNING":
        return {"status": "ALREADY_RUNNING", "decision": decision,
                "execution": False}

    result = client.start()
    output = {
        "status": result.get("status"),
        "decision": decision,
        "miner": result
    }
    _audit(output)
    return output


def status():
    return {
        "miner": client.status(),
        "policy": _read(POLICY),
        "emergency_stop": EMERGENCY.exists()
    }
