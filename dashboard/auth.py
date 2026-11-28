import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(
    os.environ.get(
        "NEXUS_AUTH_DB",
        str(Path(__file__).resolve().parents[1] / "memory" / "nexus_auth.db")
    )
)

SESSION_TTL_SECONDS = 60 * 60 * 24 * 7
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15, factory=_ClosingConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_auth_db():
    with _connect() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'user')),
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_user
            ON sessions(user_id)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_expiry
            ON sessions(expires_at)
        """)


def _normalize_email(email):
    if not isinstance(email, str):
        raise ValueError("A valid email address is required.")

    email = email.strip().lower()

    if len(email) > 254 or not re.fullmatch(
        r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
        r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
        r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+",
        email
    ):
        raise ValueError("A valid email address is required.")

    return email


def _hash_password(password, salt):
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=64
    )


def _public_user(row):
    if row is None:
        return None

    return {
        "id": row["id"],
        "email": row["email"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"]
    }


def register_user(email, password):
    email = _normalize_email(email)

    if not isinstance(password, str) or not 12 <= len(password) <= 1024:
        raise ValueError("Password must contain 12 to 1024 characters.")

    salt = secrets.token_bytes(16)
    password_hash = _hash_password(password, salt)
    now = int(time.time())

    initialize_auth_db()

    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")

        existing = connection.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing:
            raise ValueError("An account with this email already exists.")

        role = "user"

        cursor = connection.execute("""
            INSERT INTO users
                (email, password_hash, password_salt, role, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            email,
            password_hash.hex(),
            salt.hex(),
            role,
            now
        ))

        row = connection.execute(
            "SELECT * FROM users WHERE id = ?",
            (cursor.lastrowid,)
        ).fetchone()

        connection.commit()
        return _public_user(row)

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()



def bootstrap_admin(email, password):
    """Create the first administrator through a local operator-controlled action."""
    email = _normalize_email(email)

    if not isinstance(password, str) or not 12 <= len(password) <= 1024:
        raise ValueError("Password must contain 12 to 1024 characters.")

    salt = secrets.token_bytes(16)
    password_hash = _hash_password(password, salt)
    now = int(time.time())

    initialize_auth_db()

    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")

        existing_admin = connection.execute(
            "SELECT id FROM users WHERE role = 'admin' LIMIT 1"
        ).fetchone()

        if existing_admin:
            raise ValueError("An administrator already exists. Bootstrap refused.")

        existing_user = connection.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing_user:
            raise ValueError("An account with this email already exists.")

        cursor = connection.execute("""
            INSERT INTO users
                (email, password_hash, password_salt, role, created_at)
            VALUES (?, ?, ?, 'admin', ?)
        """, (
            email,
            password_hash.hex(),
            salt.hex(),
            now
        ))

        row = connection.execute(
            "SELECT * FROM users WHERE id = ?",
            (cursor.lastrowid,)
        ).fetchone()

        connection.commit()
        return _public_user(row)

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def authenticate_user(email, password):
    try:
        email = _normalize_email(email)
    except ValueError:
        return None

    if not isinstance(password, str) or len(password) > 1024:
        return None

    initialize_auth_db()

    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1",
            (email,)
        ).fetchone()

    if row is None:
        return None

    try:
        salt = bytes.fromhex(row["password_salt"])
        expected = bytes.fromhex(row["password_hash"])
        actual = _hash_password(password, salt)
    except (ValueError, TypeError):
        return None

    if not hmac.compare_digest(actual, expected):
        return None

    return _public_user(row)


def create_session(user_id, ttl_seconds=SESSION_TTL_SECONDS):
    if not isinstance(user_id, int) or user_id < 1:
        raise ValueError("Invalid user ID.")

    if not isinstance(ttl_seconds, int) or not 60 <= ttl_seconds <= 30 * 86400:
        raise ValueError("Invalid session lifetime.")

    initialize_auth_db()

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = int(time.time())

    with _connect() as connection:
        user = connection.execute(
            "SELECT id FROM users WHERE id = ? AND is_active = 1",
            (user_id,)
        ).fetchone()

        if user is None:
            raise ValueError("Account is unavailable.")

        connection.execute(
            "DELETE FROM sessions WHERE expires_at <= ?",
            (now,)
        )

        connection.execute("""
            INSERT INTO sessions (user_id, token_hash, expires_at, created_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, token_hash, now + ttl_seconds, now))

    return token


def get_session_user(token):
    if not isinstance(token, str) or not 20 <= len(token) <= 256:
        return None

    initialize_auth_db()

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = int(time.time())

    with _connect() as connection:
        row = connection.execute("""
            SELECT users.*
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ?
              AND sessions.expires_at > ?
              AND users.is_active = 1
        """, (token_hash, now)).fetchone()

    return _public_user(row)


def revoke_session(token):
    if not isinstance(token, str) or not 20 <= len(token) <= 256:
        return

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    initialize_auth_db()

    with _connect() as connection:
        connection.execute(
            "DELETE FROM sessions WHERE token_hash = ?",
            (token_hash,)
        )


def get_user_count():
    initialize_auth_db()

    with _connect() as connection:
        return connection.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]
