"""Configurable multi-provider mining market data adapter."""

import json
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "config" / "xmrig.market_sources.json"
MARKET = ROOT / "config" / "xmrig.market.json"
MAX_RESPONSE = 1_000_000
MAX_AGE = 900


def _read(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


def _fetch(source):
    url = source.get("url", "")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise ValueError("Market providers must use HTTPS.")

    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "NEXUS-AI-Market/1.0"}
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError("Market provider returned an unsuccessful response.")
        raw = response.read(MAX_RESPONSE + 1)

    if len(raw) > MAX_RESPONSE:
        raise ValueError("Market provider response exceeded size limit.")

    return json.loads(raw.decode("utf-8"))


def _normalize(payload, source):
    if not isinstance(payload, dict):
        raise ValueError("Invalid provider response.")

    opportunities = payload.get("opportunities")
    if not isinstance(opportunities, list):
        raise ValueError("Provider must return an opportunities list.")

    now = time.time()
    output = []

    for item in opportunities:
        if not isinstance(item, dict):
            continue

        try:
            timestamp = float(item["timestamp"])
            revenue = float(item["estimated_revenue_per_day"])
            fee = float(item.get("pool_fee_percent", 0))
            power = float(item["estimated_power_watts"])
            confidence = float(item.get("confidence", 0.8))

            if now - timestamp < 0 or now - timestamp > MAX_AGE:
                continue
            if revenue < 0 or power <= 0 or not 0 <= fee <= 100:
                continue
            if not 0 < confidence <= 1:
                continue

            coin = str(item["coin"]).strip().lower()
            algorithm = str(item["algorithm"]).strip()

            if not coin or not algorithm:
                continue

            output.append({
                "coin": coin,
                "algorithm": algorithm,
                "estimated_revenue_per_day": revenue,
                "pool_fee_percent": fee,
                "estimated_power_watts": power,
                "confidence": confidence,
                "timestamp": timestamp,
                "provider": str(source.get("name", "unnamed"))
            })
        except (KeyError, TypeError, ValueError):
            continue

    return output


def refresh():
    config = _read(SOURCES, {})
    sources = config.get("providers", [])

    if not isinstance(sources, list) or not sources:
        return {"status": "NO_PROVIDERS_CONFIGURED", "count": 0}

    combined = []
    errors = []

    for source in sources:
        if not isinstance(source, dict) or source.get("enabled") is not True:
            continue

        try:
            payload = _fetch(source)
            combined.extend(_normalize(payload, source))
        except Exception as exc:
            errors.append({
                "provider": str(source.get("name", "unnamed")),
                "error": type(exc).__name__
            })

    # Keep only the freshest observation per coin and algorithm.
    freshest = {}
    for item in combined:
        key = (item["coin"], item["algorithm"].lower())
        if key not in freshest or item["timestamp"] > freshest[key]["timestamp"]:
            freshest[key] = item

    result = {
        "updated_at": time.time(),
        "opportunities": list(freshest.values()),
        "provider_errors": errors
    }

    MARKET.parent.mkdir(parents=True, exist_ok=True)
    temp = MARKET.with_suffix(".tmp")
    temp.write_text(json.dumps(result, indent=2), encoding="utf-8")
    temp.replace(MARKET)

    return {
        "status": "UPDATED" if freshest else "NO_VALID_MARKET_DATA",
        "count": len(freshest),
        "provider_errors": len(errors)
    }


def get_opportunities():
    data = _read(MARKET, {})
    if time.time() - float(data.get("updated_at", 0)) > MAX_AGE:
        return []
    return data.get("opportunities", [])
