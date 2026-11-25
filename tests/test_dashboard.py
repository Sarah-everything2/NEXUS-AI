import unittest
from fastapi.testclient import TestClient
from dashboard.app import app

class TestDashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_homepage(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("NEXUS AI", r.text)

    def test_status(self):
        r = self.client.get("/api/status")
        self.assertEqual(r.status_code, 200)
        for key in ("name", "version", "agents", "skills", "tools"):
            self.assertIn(key, r.json())

    def test_catalog_routes(self):
        for route in ("/api/agents", "/api/skills", "/api/tools"):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 200)

if __name__ == "__main__":
    unittest.main()
