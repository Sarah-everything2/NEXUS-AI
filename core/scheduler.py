import asyncio
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler


DB_PATH = Path(__file__).resolve().parent.parent / "memory" / "nexus_memory.db"

scheduler = AsyncIOScheduler(timezone="UTC")


def initialize():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                run_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                repeat TEXT DEFAULT 'once'
            )
        """)

        columns = [
            row[1] for row in connection.execute(
                "PRAGMA table_info(scheduled_tasks)"
            )
        ]

        if "repeat" not in columns:
            connection.execute(
                "ALTER TABLE scheduled_tasks ADD COLUMN repeat TEXT DEFAULT 'once'"
            )


def add_reminder(minutes, message, repeat="once"):
    if minutes < 1:
        raise ValueError("Reminder must be at least 1 minute away.")

    if not message.strip():
        raise ValueError("Reminder message cannot be empty.")

    if repeat not in ("once", "hourly", "daily", "weekly"):
        raise ValueError("Invalid repeat interval.")

    initialize()

    run_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.execute(
            """
            INSERT INTO scheduled_tasks
            (message, run_at, status, created_at, repeat)
            VALUES (?, ?, 'pending', ?, ?)
            """,
            (
                message.strip(),
                run_at.isoformat(),
                datetime.now(timezone.utc).isoformat(),
                repeat
            )
        )

        task_id = cursor.lastrowid

    schedule_job(task_id, message.strip(), run_at, repeat)

    return {
        "id": task_id,
        "message": message.strip(),
        "run_at": run_at.isoformat(),
        "repeat": repeat
    }


def schedule_job(task_id, message, run_at, repeat):
    if repeat == "once":
        scheduler.add_job(
            deliver_reminder,
            "date",
            run_date=run_at,
            args=[task_id, message],
            id=str(task_id),
            replace_existing=True
        )
    else:
        scheduler.add_job(
            deliver_reminder,
            "interval",
            **{
                "hours": 1 if repeat == "hourly" else 0,
                "days": 1 if repeat == "daily" else 0,
                "weeks": 1 if repeat == "weekly" else 0,
            },
            start_date=run_at,
            args=[task_id, message],
            id=str(task_id),
            replace_existing=True
        )


async def deliver_reminder(task_id, message):
    print(f"\n\n[ NEXUS REMINDER #{task_id} ]")
    print(f"  {message}")
    print("  Reminder delivered.\n")

    with sqlite3.connect(DB_PATH) as connection:
        row = connection.execute(
            "SELECT repeat FROM scheduled_tasks WHERE id = ? AND status = 'pending'",
            (task_id,)
        ).fetchone()

        if row and row[0] == "once":
            connection.execute(
                "UPDATE scheduled_tasks SET status = 'completed' WHERE id = ?",
                (task_id,)
            )


def list_reminders():
    initialize()

    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute("""
            SELECT id, message, run_at, status, repeat
            FROM scheduled_tasks
            WHERE status = 'pending'
            ORDER BY run_at
        """).fetchall()

    return [dict(row) for row in rows]


def cancel_reminder(task_id):
    initialize()

    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.execute("""
            UPDATE scheduled_tasks
            SET status = 'cancelled'
            WHERE id = ? AND status = 'pending'
        """, (task_id,))

    if cursor.rowcount:
        job = scheduler.get_job(str(task_id))
        if job:
            scheduler.remove_job(str(task_id))
        return True

    return False


def start_scheduler():
    initialize()

    if not scheduler.running:
        scheduler.start()

    with sqlite3.connect(DB_PATH) as connection:
        rows = connection.execute("""
            SELECT id, message, run_at, repeat
            FROM scheduled_tasks
            WHERE status = 'pending'
        """).fetchall()

    now = datetime.now(timezone.utc)

    for task_id, message, run_at, repeat in rows:
        scheduled_time = datetime.fromisoformat(run_at)

        if scheduled_time <= now:
            scheduled_time = now + timedelta(seconds=2)

        schedule_job(task_id, message, scheduled_time, repeat)


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)