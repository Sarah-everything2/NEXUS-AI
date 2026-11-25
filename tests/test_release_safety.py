import json
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "trading_safety.demo.json"

BRIDGE_ROOT = Path(
    os.environ.get("MT5_BRIDGE_ROOT", r"C:\AI-Trading\mt5-bridge")
)
CONFIG = BRIDGE_ROOT / "config" / "trading_safety.json"
WORKER = BRIDGE_ROOT / "strategy" / "auto_demo_worker.py"
API = BRIDGE_ROOT / "mt5_api.py"


class TestReleaseSafety(unittest.TestCase):

    def config(self):
        path = CONFIG if CONFIG.is_file() else FIXTURE
        self.assertTrue(path.is_file(), f"Safety policy missing: {path}")
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def test_demo_only(self):
        self.assertIs(self.config().get("demo_only"), True)

    def test_live_execution_disabled(self):
        self.assertIs(self.config().get("live_execution_enabled"), False)

    def test_confirmation_and_protection(self):
        c = self.config()
        self.assertIs(c.get("require_confirmation"), True)
        self.assertIs(c.get("require_stop_loss"), True)
        self.assertIs(c.get("require_take_profit"), True)

    def test_autonomous_demo_gates(self):
        c = self.config()
        self.assertIs(c.get("automatic_demo_trading_enabled"), True)
        self.assertIs(c.get("demo_execution_enabled"), True)
        self.assertIs(c.get("execution_enabled"), True)

    def test_risk_limits(self):
        c = self.config()
        self.assertLessEqual(float(c["maximum_volume"]), 0.01)
        self.assertLessEqual(float(c["maximum_risk_percent"]), 1.0)
        self.assertLessEqual(int(c["maximum_open_positions"]), 1)
        self.assertGreater(float(c["maximum_risk_percent"]), 0)

    def test_quote_age_limit(self):
        self.assertLessEqual(
            int(self.config()["maximum_quote_age_seconds"]), 300
        )

    def test_worker_demo_identity_guards(self):
        if not WORKER.is_file():
            self.skipTest("MT5 bridge worker unavailable on this runner")
        source = WORKER.read_text(encoding="utf-8-sig")
        self.assertIn("MT5_EXPECTED_LOGIN", source)
        self.assertIn("ACCOUNT_TRADE_MODE_DEMO", source)
        self.assertIn("headway", source.lower())

    def test_worker_emergency_stop_guard(self):
        if not WORKER.is_file():
            self.skipTest("MT5 bridge worker unavailable on this runner")
        source = WORKER.read_text(encoding="utf-8-sig")
        self.assertIn("emergency_stop.flag", source)

    def test_worker_uses_unadjusted_mt5_timestamp(self):
        if not WORKER.is_file():
            self.skipTest("MT5 bridge worker unavailable on this runner")
        source = WORKER.read_text(encoding="utf-8-sig")
        self.assertIn("tick.time_msc / 1000", source)
        self.assertNotIn("BROKER_UTC_OFFSET_HOURS", source)

    def test_api_trade_symbol_restrictions(self):
        if not API.is_file():
            self.skipTest("MT5 bridge API unavailable on this runner")
        source = API.read_text(encoding="utf-8-sig")
        self.assertIn('trade.symbol != "XAUUSD"', source)
        self.assertGreaterEqual(
            source.count("Only XAUUSD is permitted"), 2
        )
        self.assertNotIn("BROKER_UTC_OFFSET_HOURS", source)

    def test_api_uses_unadjusted_mt5_timestamp(self):
        if not API.is_file():
            self.skipTest("MT5 bridge API unavailable on this runner")
        source = API.read_text(encoding="utf-8-sig")
        self.assertIn("tick.time_msc / 1000", source)

    def test_no_obvious_secret_files_tracked(self):
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True
        )
        tracked = result.stdout.lower().splitlines()
        forbidden = [
            p for p in tracked
            if p.endswith(".env")
            or p.endswith((
                "id_rsa",
                "id_ed25519",
                "token.json",
                "credentials.json"
            ))
            or "secrets/" in p
        ]
        self.assertEqual(forbidden, [])


if __name__ == "__main__":
    unittest.main()
