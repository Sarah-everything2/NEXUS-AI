import tempfile
import unittest
from pathlib import Path

from dashboard import auth


class AuthenticationSecurityTests(unittest.TestCase):
    def setUp(self):
        self.original_db_path = auth.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        auth.DB_PATH = Path(self.temp_dir.name) / "auth_test.db"

    def tearDown(self):
        auth.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_public_registration_never_creates_admin(self):
        user = auth.register_user(
            "first@example.com",
            "RegularUser-Password-2026"
        )
        self.assertEqual(user["role"], "user")

    def test_bootstrap_creates_admin_after_regular_users_exist(self):
        auth.register_user(
            "user@example.com",
            "RegularUser-Password-2026"
        )

        admin = auth.bootstrap_admin(
            "admin@example.com",
            "SecureAdmin-Password-2026"
        )
        self.assertEqual(admin["role"], "admin")

    def test_second_admin_bootstrap_is_rejected(self):
        auth.bootstrap_admin(
            "admin@example.com",
            "SecureAdmin-Password-2026"
        )

        with self.assertRaisesRegex(ValueError, "administrator already exists"):
            auth.bootstrap_admin(
                "second-admin@example.com",
                "AnotherAdmin-Password-2026"
            )

    def test_bootstrap_rejects_existing_user_email(self):
        auth.register_user(
            "existing@example.com",
            "RegularUser-Password-2026"
        )

        with self.assertRaisesRegex(ValueError, "account with this email"):
            auth.bootstrap_admin(
                "existing@example.com",
                "SecureAdmin-Password-2026"
            )

    def test_registration_after_admin_remains_standard_user(self):
        auth.bootstrap_admin(
            "admin@example.com",
            "SecureAdmin-Password-2026"
        )

        user = auth.register_user(
            "new-user@example.com",
            "RegularUser-Password-2026"
        )
        self.assertEqual(user["role"], "user")


if __name__ == "__main__":
    unittest.main()
