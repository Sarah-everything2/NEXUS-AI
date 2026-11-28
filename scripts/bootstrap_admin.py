from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import sqlite3
from datetime import datetime
from getpass import getpass
from pathlib import Path
from dashboard import auth

expected_db = (Path.cwd() / "memory" / "nexus_auth.db").resolve()
db_path = auth.DB_PATH.resolve()

if db_path != expected_db:
    raise SystemExit(f"ABORTED: unexpected database path: {db_path}")

if auth.get_user_count() != 0:
    raise SystemExit("ABORTED: database is no longer empty.")

backup_path = db_path.with_name(
    f"nexus_auth_pre_admin_{datetime.now():%Y%m%d_%H%M%S}.bak"
)

source = sqlite3.connect(str(db_path))
backup = sqlite3.connect(str(backup_path))
try:
    source.backup(backup)
finally:
    backup.close()
    source.close()

print("DATABASE BACKUP:", backup_path)

email = input("Administrator email: ").strip()
password = getpass("Administrator password: ")
confirmation = getpass("Confirm administrator password: ")

if password != confirmation:
    raise SystemExit("ABORTED: passwords do not match.")

user = auth.bootstrap_admin(email, password)
verified = auth.authenticate_user(email, password)

if not verified or verified["role"] != "admin":
    raise SystemExit("ERROR: administrator verification failed.")

print("\nADMINISTRATOR CREATED AND VERIFIED")
print("EMAIL:", user["email"])
print("ROLE:", verified["role"])
print("ACCOUNT ID:", verified["id"])
