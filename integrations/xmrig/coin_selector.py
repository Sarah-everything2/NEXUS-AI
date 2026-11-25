"""NEXUS multi-coin profitability and resource-aware selection engine."""

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILES = ROOT / "config" / "xmrig.profiles.json"

DEFAULTS = {
    "minimum_net_profit_per_day": 0.0,
    "maximum_power_watts": 150,
    "maximum_cpu_percent": 75,
    "minimum_available_ram_gb": 2.5,
    "maximum_temperature_c": 80,
    "maximum_pool_fee_percent": 3.0,
    "maximum_data_age_seconds": 900,
    "minimum_profit_improvement_percent": 10
}


def _profiles():
    try:
        return json.loads(PROFILES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def evaluate_opportunities(
    opportunities,
    electricity_price_per_kwh,
    hardware,
    settings=None
):
    """Rank supplied market snapshots. Does not connect to pools or start miners."""
    cfg = {**DEFAULTS, **(settings or {})}
    now = time.time()

    if not isinstance(opportunities, list) or not opportunities:
        return {"status": "NO_DATA", "selected": None, "ranked": []}

    if not isinstance(hardware, dict):
        return {"status": "BLOCKED", "reason": "Hardware telemetry unavailable",
                "selected": None, "ranked": []}

    try:
        electricity = float(electricity_price_per_kwh)
        ram = float(hardware["available_ram_gb"])
        cpu = float(hardware["cpu_percent"])
        power = float(hardware["estimated_power_watts"])
        temperature = float(hardware["temperature_c"])
    except (KeyError, TypeError, ValueError):
        return {"status": "BLOCKED", "reason": "Incomplete hardware or electricity data",
                "selected": None, "ranked": []}

    if electricity < 0:
        return {"status": "BLOCKED", "reason": "Invalid electricity price",
                "selected": None, "ranked": []}

    if (
        ram < cfg["minimum_available_ram_gb"]
        or cpu > cfg["maximum_cpu_percent"]
        or power > cfg["maximum_power_watts"]
        or temperature >= cfg["maximum_temperature_c"]
    ):
        return {
            "status": "BLOCKED",
            "reason": "Hardware resource or temperature safety limit reached",
            "selected": None,
            "ranked": []
        }

    configured = _profiles()
    ranked = []

    for item in opportunities:
        try:
            coin = str(item["coin"]).strip().lower()
            algorithm = str(item["algorithm"]).strip()
            revenue = float(item["estimated_revenue_per_day"])
            fee = float(item.get("pool_fee_percent", 0))
            age = now - float(item["timestamp"])
            watts = float(item.get("estimated_power_watts", power))
            confidence = float(item.get("confidence", 1.0))

            if coin not in configured:
                continue
            if algorithm.lower() != str(configured[coin]["algorithm"]).lower():
                continue
            if revenue < 0 or watts <= 0 or fee < 0 or confidence < 0 or confidence > 1:
                continue
            if fee > cfg["maximum_pool_fee_percent"]:
                continue
            if age < 0 or age > cfg["maximum_data_age_seconds"]:
                continue
            if watts > cfg["maximum_power_watts"]:
                continue

            gross = revenue * (1 - fee / 100)
            electricity_cost = (watts / 1000) * 24 * electricity
            net = (gross - electricity_cost) * confidence

            ranked.append({
                "coin": coin,
                "algorithm": algorithm,
                "estimated_gross_revenue_per_day": round(gross, 6),
                "estimated_electricity_cost_per_day": round(electricity_cost, 6),
                "estimated_net_profit_per_day": round(net, 6),
                "confidence": confidence,
                "data_age_seconds": round(age, 1)
            })
        except (KeyError, TypeError, ValueError):
            continue

    ranked.sort(key=lambda x: x["estimated_net_profit_per_day"], reverse=True)
    eligible = [
        x for x in ranked
        if x["estimated_net_profit_per_day"] >= cfg["minimum_net_profit_per_day"]
    ]

    if not eligible:
        return {
            "status": "NO_PROFITABLE_COIN",
            "selected": None,
            "ranked": ranked
        }

    return {
        "status": "RECOMMENDATION_READY",
        "selected": eligible[0],
        "ranked": ranked,
        "execution_authorized": False,
        "note": "Recommendation only. Central Brain must enforce its operating policy."
    }


def should_switch(current_coin, candidate, settings=None):
    """Avoid unnecessary switching unless improvement clears configured threshold."""
    cfg = {**DEFAULTS, **(settings or {})}

    if not candidate or not candidate.get("coin"):
        return False

    if str(current_coin or "").lower() == candidate["coin"].lower():
        return False

    improvement = candidate.get("estimated_net_profit_per_day")
    if not isinstance(improvement, (int, float)):
        return False

    return improvement > 0 and improvement >= cfg["minimum_net_profit_per_day"]


def should_switch(current_coin, candidate, settings=None):
    """Switch only when a candidate materially outperforms the current coin."""
    settings = settings or {}
    if not isinstance(current_coin, dict) or not isinstance(candidate, dict):
        return False

    try:
        current_net = float(current_coin["net_profit_per_day"])
        candidate_net = float(candidate["net_profit_per_day"])
        minimum_net = float(settings.get("min_net_profit_per_day", 0))
        improvement = float(settings.get("min_profit_improvement_percent", 10))
        minimum_absolute = float(settings.get("min_absolute_profit_improvement", 0))
    except (KeyError, TypeError, ValueError):
        return False

    if candidate_net <= minimum_net or current_net <= 0:
        return False

    required_gain = max(
        current_net * improvement / 100,
        minimum_absolute
    )
    return candidate_net - current_net >= required_gain


def build_measured_opportunities(networks, prices, performance, hardware,
                                 pool_fee_percent=1.0):
    """Estimate daily mining revenue from measured hashrate and network data.

    prices: {"coin_name": {"price_usd": 1.23, "timestamp": 1234567890}}
    Hardware power is explicitly an estimate unless externally measured.
    """
    import time

    if not isinstance(performance, dict) or not isinstance(hardware, dict):
        return []

    now = time.time()
    if now - float(performance.get("timestamp", 0)) > 120:
        return []

    hashrate = float(performance.get("hashrate_10s", 0))
    power = float(hardware.get("estimated_power_watts", 0))

    if hashrate <= 0 or power <= 0:
        return []

    opportunities = []

    for network in networks:
        coin = str(network.get("coin", "")).lower()
        price_data = prices.get(coin, {})
        try:
            difficulty = float(network["difficulty"])
            reward = float(network["block_reward"])
            target = float(network["block_target_seconds"])
            price = float(price_data["price_usd"])
            price_time = float(price_data["timestamp"])

            if now - price_time > 900 or price_time > now + 60:
                continue
            if min(difficulty, reward, target, price) <= 0:
                continue

            expected_coins_day = (
                hashrate * 86400 / difficulty * reward
            )
            revenue = expected_coins_day * price

            opportunities.append({
                "coin": coin,
                "algorithm": network["algorithm"],
                "estimated_revenue_per_day": revenue,
                "pool_fee_percent": float(pool_fee_percent),
                "estimated_power_watts": power,
                "confidence": 0.8,
                "timestamp": now,
                "hashrate_used": hashrate,
                "market_price_usd": price,
                "revenue_basis": "measured_hashrate_network_difficulty",
                "power_basis": "hardware_estimate"
            })
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue

    return opportunities
