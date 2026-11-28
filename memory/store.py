import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "nexus_memory.db"


def initialize():
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)

        columns = {
            row[1] for row in connection.execute(
                "PRAGMA table_info(conversations)"
            ).fetchall()
        }
        if "user_id" not in columns:
            connection.execute(
                "ALTER TABLE conversations ADD COLUMN user_id TEXT"
            )

        connection.execute("""
            CREATE TABLE IF NOT EXISTS research_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS research_results_user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                UNIQUE(user_id, url)
            )
        """)


def save_message(role, content, user_id=None):
    if role not in ("user", "assistant", "system"):
        raise ValueError("Invalid message role")

    initialize()
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO conversations
            (role, content, timestamp, user_id)
            VALUES (?, ?, ?, ?)
            """,
            (
                role,
                content,
                datetime.now(timezone.utc).isoformat(),
                str(user_id) if user_id is not None else None
            )
        )


def get_recent_messages(limit=20, user_id=None, is_admin=False):
    if limit < 1:
        raise ValueError("Limit must be positive")

    initialize()
    with sqlite3.connect(DB_PATH) as connection:
        if user_id is None:
            rows = connection.execute(
                """
                SELECT role, content FROM conversations
                WHERE user_id IS NULL
                ORDER BY id DESC LIMIT ?
                """,
                (limit,)
            ).fetchall()
        elif is_admin:
            rows = connection.execute(
                """
                SELECT role, content FROM conversations
                WHERE user_id = ? OR user_id IS NULL
                ORDER BY id DESC LIMIT ?
                """,
                (str(user_id), limit)
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT role, content FROM conversations
                WHERE user_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (str(user_id), limit)
            ).fetchall()

    return [
        {"role": role, "content": content}
        for role, content in reversed(rows)
    ]


def save_research(url, title, content, user_id=None):
    initialize()
    timestamp = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DB_PATH) as connection:
        if user_id is None:
            connection.execute(
                """
                INSERT INTO research_results
                (url, title, content, timestamp)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    title=excluded.title,
                    content=excluded.content,
                    timestamp=excluded.timestamp
                """,
                (url, title, content[:10000], timestamp)
            )
        else:
            connection.execute(
                """
                INSERT INTO research_results_user
                (user_id, url, title, content, timestamp)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, url) DO UPDATE SET
                    title=excluded.title,
                    content=excluded.content,
                    timestamp=excluded.timestamp
                """,
                (str(user_id), url, title, content[:10000], timestamp)
            )

    return {"status": "SAVED", "url": url, "title": title}


def search_research(query, limit=10, user_id=None, is_admin=False):
    if not query.strip():
        raise ValueError("Search query cannot be empty")
    if limit < 1:
        raise ValueError("Limit must be positive")

    initialize()
    pattern = f"%{query}%"

    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row

        if user_id is None:
            rows = connection.execute(
                """
                SELECT url, title, content, timestamp
                FROM research_results
                WHERE title LIKE ? OR content LIKE ? OR url LIKE ?
                ORDER BY id DESC LIMIT ?
                """,
                (pattern, pattern, pattern, limit)
            ).fetchall()
        elif is_admin:
            rows = connection.execute(
                """
                SELECT url, title, content, timestamp FROM (
                    SELECT url, title, content, timestamp, id
                    FROM research_results_user
                    WHERE user_id = ?
                      AND (title LIKE ? OR content LIKE ? OR url LIKE ?)
                    UNION ALL
                    SELECT url, title, content, timestamp, id
                    FROM research_results
                    WHERE title LIKE ? OR content LIKE ? OR url LIKE ?
                )
                ORDER BY id DESC LIMIT ?
                """,
                (
                    str(user_id),
                    pattern, pattern, pattern,
                    pattern, pattern, pattern,
                    limit
                )
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT url, title, content, timestamp
                FROM research_results_user
                WHERE user_id = ?
                  AND (title LIKE ? OR content LIKE ? OR url LIKE ?)
                ORDER BY id DESC LIMIT ?
                """,
                (str(user_id), pattern, pattern, pattern, limit)
            ).fetchall()

    return [dict(row) for row in rows]


if __name__ == "__main__":
    initialize()
    print("NEXUS AI MEMORY ENGINE")
    print("Database:", DB_PATH)
    print("Status: READY")
