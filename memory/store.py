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

        connection.execute("""
            CREATE TABLE IF NOT EXISTS research_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)


def save_message(role, content):

    if role not in ("user", "assistant", "system"):
        raise ValueError("Invalid message role")

    initialize()

    with sqlite3.connect(DB_PATH) as connection:

        connection.execute(
            """
            INSERT INTO conversations
            (role, content, timestamp)
            VALUES (?, ?, ?)
            """,
            (
                role,
                content,
                datetime.now(timezone.utc).isoformat()
            )
        )


def get_recent_messages(limit=20):

    if limit < 1:
        raise ValueError("Limit must be positive")

    initialize()

    with sqlite3.connect(DB_PATH) as connection:

        rows = connection.execute(
            """
            SELECT role, content
            FROM conversations
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

    return [
        {"role": role, "content": content}
        for role, content in reversed(rows)
    ]


def save_research(url, title, content):

    initialize()

    with sqlite3.connect(DB_PATH) as connection:

        connection.execute(
            """
            INSERT INTO research_results
            (url, title, content, timestamp)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title = excluded.title,
                content = excluded.content,
                timestamp = excluded.timestamp
            """,
            (
                url,
                title,
                content[:10000],
                datetime.now(timezone.utc).isoformat()
            )
        )

    return {
        "status": "SAVED",
        "url": url,
        "title": title
    }


def search_research(query, limit=10):

    if not query.strip():
        raise ValueError("Search query cannot be empty")

    if limit < 1:
        raise ValueError("Limit must be positive")

    initialize()

    pattern = f"%{query}%"

    with sqlite3.connect(DB_PATH) as connection:

        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT url, title, content, timestamp
            FROM research_results
            WHERE title LIKE ? OR content LIKE ? OR url LIKE ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (pattern, pattern, pattern, limit)
        ).fetchall()

    return [dict(row) for row in rows]


if __name__ == "__main__":

    initialize()

    print("NEXUS AI MEMORY ENGINE")
    print("----------------------")
    print("Conversation memory: ENABLED")
    print("Research memory: ENABLED")
    print("Database:", DB_PATH)
    print("Status: READY")