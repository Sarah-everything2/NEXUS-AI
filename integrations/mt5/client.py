import csv
import re
from pathlib import Path



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
    import httpx
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
    """Read the latest signal directly from the existing Hermes strategy engine."""
    import importlib.util

    engine_path = Path(
        r"C:\AI-Trading\mt5-bridge\strategy\mt5_signal_engine.py"
    )

    try:
        spec = importlib.util.spec_from_file_location(
            "nexus_mt5_signal_engine", engine_path
        )
        if spec is None or spec.loader is None:
            return {
                "status": "ERROR",
                "message": "Could not load the MT5 strategy engine.",
            }

        engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(engine)

        signal = engine.get_latest_signal()

        if not isinstance(signal, dict) or not signal.get("ok"):
            return {
                "status": "ERROR",
                "message": "Strategy engine did not return a valid signal.",
                "details": signal,
            }

        return {
            "status": "SUCCESS",
            "mode": "READ ONLY",
            "latest_signal": signal,
        }

    except Exception as exc:
        return {
            "status": "ERROR",
            "message": f"Could not read MT5 strategy signal: {exc}",
        }
