"""NEXUS autonomous mining decision and execution coordinator."""

import json
import math
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


def _safety_stop(reason):
    """Stop an active miner when a mandatory safety policy blocks mining."""
    try:
        current = client.status()
    except Exception as exc:
        return {
            "status": "SAFETY_STOP_FAILED",
            "reason": f"Could not verify miner status: {exc}",
            "execution": False
        }

    if not isinstance(current, dict):
        return {
            "status": "SAFETY_STOP_FAILED",
            "reason": "Miner status response is invalid",
            "execution": False
        }

    if current.get("status") == "RUNNING":
        try:
            stopped = client.stop()
            return {
                "status": reason,
                "execution": False,
                "stop": stopped
            }
        except Exception as exc:
            return {
                "status": "SAFETY_STOP_FAILED",
                "reason": str(exc),
                "execution": False
            }

    return {"status": reason, "execution": False}


def run_cycle(opportunities, electricity_price_per_kwh, hardware):
    """Evaluate mining. Execution occurs only when policy explicitly permits it."""
    policy = _read(POLICY)

    if EMERGENCY.exists():
        result = _safety_stop("EMERGENCY_STOP")
        _audit(result)
        return result

    if not isinstance(policy, dict):
        result = {"status": "BLOCKED", "reason": "Mining policy is invalid",
                  "execution": False}
        _audit(result)
        return result

    if policy.get("mining_enabled") is not True:
        result = _safety_stop("DISABLED")
        _audit(result)
        return result

    if (isinstance(electricity_price_per_kwh, bool)
            or not isinstance(electricity_price_per_kwh, (int, float))
            or not math.isfinite(electricity_price_per_kwh)
            or electricity_price_per_kwh < 0):
        result = {"status": "BLOCKED", "reason": "Valid electricity price required"}
        _audit(result)
        return result

    limits = policy.get("profitability_limits", {})
    if not isinstance(limits, dict):
        result = {"status": "BLOCKED",
                  "reason": "Profitability limits policy is invalid",
                  "execution": False}
        _audit(result)
        return result

    try:
        decision = evaluate_opportunities(
            opportunities,
            electricity_price_per_kwh,
            hardware,
            settings={
                **limits,
                "minimum_available_ram_gb": policy.get(
                    "minimum_available_ram_gb", 1.5
                ),
            }
        )
    except Exception as exc:
        result = {"status": "BLOCKED",
                  "reason": f"Profitability evaluation failed: {exc}",
                  "execution": False}
        _audit(result)
        return result

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
        output = {"status": "RECOMMENDATION_ONLY", "decision": decision,
                  "execution": False}
        _audit(output)
        return output

    if EMERGENCY.exists():
        result = _safety_stop("EMERGENCY_STOP")
        result["decision"] = decision
        _audit(result)
        return result

    recovery = client.recovery_check(
        profitability_decision=decision
    )

    if recovery.get("status") != "IDLE":
        output = {
            "status": recovery.get("status"),
            "decision": decision,
            "recovery": recovery,
            "execution": recovery.get("status") in ("RUNNING", "RESTARTED")
        }
        _audit(output)
        return output

    current = client.status()
    if current["status"] == "RUNNING":
        return {"status": "ALREADY_RUNNING", "decision": decision,
                "execution": False}

    try:
        result = client.start(profitability_decision=decision)
        output = {
            "status": result.get("status"),
            "decision": decision,
            "miner": result
        }
    except Exception as exc:
        output = {
            "status": "START_BLOCKED",
            "decision": decision,
            "reason": str(exc),
            "execution": False
        }

    _audit(output)
    return output


def status():
    return {
        "miner": client.status(),
        "policy": _read(POLICY),
        "emergency_stop": EMERGENCY.exists()
    }
