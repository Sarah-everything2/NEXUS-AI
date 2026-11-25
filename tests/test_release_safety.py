import json
import subprocess
import unittest
from pathlib import Path

CONFIG = Path("C:/AI-Trading/mt5-bridge/config/trading_safety.json")
WORKER = Path("C:/AI-Trading/mt5-bridge/strategy/auto_demo_worker.py")

class TestReleaseSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CONFIG.is_file():
            raise unittest.SkipTest("MT5 safety config unavailable")

    def config(self):
        return json.loads(CONFIG.read_text(encoding="utf-8-sig"))

    def test_demo_only(self):
        self.assertIs(self.config().get("demo_only"), True)

    def test_live_execution_disabled(self):
        self.assertIs(self.config().get("live_execution_enabled"), False)

    def test_confirmation_and_protection(self):
        c = self.config()
        self.assertIs(c.get("require_confirmation"), True)
        self.assertIs(c.get("require_stop_loss"), True)
        self.assertIs(c.get("require_take_profit"), True)

    def test_risk_limits(self):
        c = self.config()
        self.assertLessEqual(float(c["maximum_volume"]), 0.01)
        self.assertLessEqual(float(c["maximum_risk_percent"]), 1.0)
        self.assertLessEqual(int(c["maximum_open_positions"]), 1)

    def test_worker_demo_identity_guards(self):
        self.assertTrue(WORKER.is_file())
        source = WORKER.read_text(encoding="utf-8-sig")
        self.assertIn("MT5_EXPECTED_LOGIN", source)
        self.assertIn("ACCOUNT_TRADE_MODE_DEMO", source)
        self.assertIn("headway", source.lower())

    def test_worker_emergency_stop_guard(self):
        self.assertTrue(WORKER.is_file())
        self.assertIn("emergency_stop.flag", WORKER.read_text(encoding="utf-8-sig"))

    def test_no_obvious_secret_files_tracked(self):
        result = subprocess.run(
            ["git", "ls-files"], capture_output=True, text=True, check=True
        )
        tracked = result.stdout.lower().splitlines()
        forbidden = [
            p for p in tracked
            if p.endswith(".env")
            or p.endswith(("id_rsa", "id_ed25519", "token.json", "credentials.json"))
            or "secrets/" in p
        ]
        self.assertEqual(forbidden, [])

if __name__ == "__main__":
    unittest.main()
