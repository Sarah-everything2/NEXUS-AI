"""CoinGecko USD price provider with explicit coin-ID mapping."""

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAPPING = ROOT / "config" / "xmrig.coin_ids.json"
OUTPUT = ROOT / "config" / "xmrig.prices.json"
API = "https://api.coingecko.com/api/v3/simple/price"


def refresh():
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError("Configure explicit CoinGecko IDs first")

    coin_ids = sorted(set(
        str(v).strip() for v in mapping.values()
        if isinstance(v, str) and v.strip()
    ))
    if not coin_ids or len(coin_ids) > 50:
        raise ValueError("Coin ID list must contain 1-50 IDs")

    params = urllib.parse.urlencode({
        "ids": ",".join(coin_ids),
        "vs_currencies": "usd",
        "include_last_updated_at": "true"
    })
    headers = {"Accept": "application/json", "User-Agent": "NEXUS-AI/1.0"}
    api_key = os.environ.get("COINGECKO_API_KEY")
    if api_key:
        headers["x-cg-demo-api-key"] = api_key

    request = urllib.request.Request(API + "?" + params, headers=headers)
    with urllib.request.urlopen(request, timeout=12) as response:
        raw = response.read(256001)

    if len(raw) > 256000:
        raise RuntimeError("Price response too large")

    data = json.loads(raw.decode("utf-8"))
    now = time.time()
    prices = {}

    for mining_coin, coin_id in mapping.items():
        entry = data.get(coin_id, {})
        try:
            price = float(entry["usd"])
            updated = float(entry["last_updated_at"])
            if price <= 0 or updated > now + 60 or now - updated > 900:
                continue
            prices[str(mining_coin).lower()] = {
                "coin_id": coin_id,
                "price_usd": price,
                "timestamp": updated,
                "source": "CoinGecko"
            }
        except (KeyError, TypeError, ValueError):
            continue

    result = {"updated_at": now, "prices": prices}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temp = OUTPUT.with_suffix(".tmp")
    temp.write_text(json.dumps(result, indent=2), encoding="utf-8")
    temp.replace(OUTPUT)
    return {"status": "UPDATED", "price_count": len(prices)}


def get_prices(max_age_seconds=900):
    try:
        data = json.loads(OUTPUT.read_text(encoding="utf-8"))
        if time.time() - float(data["updated_at"]) > max_age_seconds:
            return {}
        return data.get("prices", {})
    except (OSError, ValueError, KeyError, TypeError):
        return {}
