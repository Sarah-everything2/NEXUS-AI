import csv
import re
from pathlib import Path

import httpx


# Fixed local Hermes bridge. No external or user-supplied URLs.
BASE_URL = "http://127.0.0.1:8001"

# Existing strategy log; do not duplicate or move it into NEXUS.
SIGNAL_LOG = (
    Path(r"C:\AI-Trading\mt5-bridge")
    / "strategy"
    / "signal_monitor_log.csv"
)

TIMEOUT = 10.0


async def _get(endpoint: str) -> dict:
    """Make a read-only request to the local Hermes bridge."""
    try:
        async with httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=TIMEOUT,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            response = await client.get(endpoint)
            response.raise_for_status()
            data = response.json()

        if not isinstance(data, dict):
            return {"status": "ERROR", "message": "Invalid bridge response."}

        if "error" in data:
            return {
                "status": "ERROR",
                "message": str(data["error"]),
            }

        return {
            "status": "SUCCESS",
            "data": data,
        }

    except httpx.TimeoutException:
        return {"status": "ERROR", "message": "MT5 bridge request timed out."}
    except httpx.HTTPStatusError as exc:
        return {
            "status": "ERROR",
            "message": f"MT5 bridge returned HTTP {exc.response.status_code}.",
        }
    except httpx.HTTPError:
        return {"status": "ERROR", "message": "MT5 bridge is unavailable."}
    except ValueError:
        return {"status": "ERROR", "message": "Invalid JSON from MT5 bridge."}


async def get_account() -> dict:
    """Read MT5 account information."""
    return await _get("/account")


async def get_price(symbol: str = "XAUUSD") -> dict:
    """Read a market quote for a broker-supported MT5 symbol."""
    if not isinstance(symbol, str) or not re.fullmatch(
        r"[A-Za-z0-9._-]{1,32}", symbol
    ):
        return {"status": "ERROR", "message": "Invalid MT5 symbol."}

    return await _get(f"/price/{symbol}")


async def get_positions() -> dict:
    """Read currently open MT5 positions."""
    return await _get("/positions")


async def get_history() -> dict:
    """Read the available 90-day MT5 demo trade history."""
    return await _get("/history")


def get_strategy_signal() -> dict:
    """Read the latest existing Hermes strategy signal."""
    if not SIGNAL_LOG.is_file():
        return {
            "status": "ERROR",
            "message": "Hermes strategy signal log not found.",
        }

    try:
        with SIGNAL_LOG.open(
            "r",
            newline="",
            encoding="utf-8-sig",
        ) as file:
            rows = list(csv.DictReader(file))

        if not rows:
            return {
                "status": "EMPTY",
                "message": "Hermes strategy signal log is empty.",
            }

        return {
            "status": "SUCCESS",
            "mode": "READ ONLY",
            "latest_signal": rows[-1],
        }

    except (OSError, csv.Error):
        return {
            "status": "ERROR",
            "message": "Could not read Hermes strategy signal log.",
        }
