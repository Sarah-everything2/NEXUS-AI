import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

# Keep dashboard tests completely separate from the real auth database.
_TEST_AUTH_DIR = tempfile.TemporaryDirectory()

from dashboard import auth as auth_module
auth_module.DB_PATH = Path(_TEST_AUTH_DIR.name) / "dashboard_test_auth.db"

from dashboard.app import app


def tearDownModule():
    _TEST_AUTH_DIR.cleanup()


class TestDashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        response = cls.client.post(
            "/auth/register",
            json={
                "email": "dashboard-test@example.com",
                "password": "TestPassword-2026-Safe"
            },
        )
        if response.status_code != 200:
            raise RuntimeError(
                "Could not create isolated dashboard test account: "
                + response.text
            )

    def test_homepage(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("NEXUS AI", response.text)

    def test_status(self):
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        for key in ("name", "version", "agents", "skills", "tools"):
            self.assertIn(key, response.json())

    def test_catalog_routes(self):
        for route in ("/api/agents", "/api/skills", "/api/tools"):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 200)

    def test_login_page_is_public(self):
        response = self.client.get("/auth/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn("NEXUS AI", response.text)

    def test_unauthenticated_dashboard_is_protected(self):
        anonymous = TestClient(app, follow_redirects=False)
        home = anonymous.get("/")
        self.assertEqual(home.status_code, 303)
        self.assertEqual(home.headers.get("location"), "/auth/login")

        status = anonymous.get("/api/status")
        self.assertEqual(status.status_code, 401)


if __name__ == "__main__":
    unittest.main()
