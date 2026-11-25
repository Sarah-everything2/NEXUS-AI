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




async def _run_video_autopilot():
    import asyncio
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    policy_path = root / "config" / "video_autopilot.policy.json"

    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))

        if not policy.get("enabled") or not policy.get("automatic_processing"):
            return {"status": "DISABLED"}

        from integrations.video_clipping.job_manager import recover_stale_jobs
        from integrations.video_clipping.video_autopilot import process_queue

        recover_stale_jobs()

        return await asyncio.to_thread(
            process_queue,
            max_jobs=policy.get("maximum_jobs_per_cycle", 1)
        )

    except Exception as exc:
        print("[VIDEO AUTOPILOT]", type(exc).__name__)
        return {"status": "ERROR", "error": type(exc).__name__}


def schedule_video_autopilot(interval_seconds=60):
    if scheduler.get_job("nexus_video_autopilot"):
        return

    scheduler.add_job(
        _run_video_autopilot,
        "interval",
        seconds=max(30, int(interval_seconds)),
        id="nexus_video_autopilot",
        max_instances=1,
        coalesce=True,
        replace_existing=True
    )



async def _run_video_publisher():
    import asyncio
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    try:
        policy = json.loads(
            (root / "config" / "video_autopilot.policy.json")
            .read_text(encoding="utf-8-sig")
        )
        if policy.get("auto_publish_enabled") is not True:
            return {"status": "PUBLISHING_DISABLED"}

        from integrations.video_clipping.video_publisher import (
            process_publication_queue
        )
        return await asyncio.to_thread(
            process_publication_queue,
            max_jobs=policy.get("maximum_publications_per_cycle", 1)
        )
    except Exception as exc:
        print("[VIDEO PUBLISHER]", type(exc).__name__)
        return {"status": "ERROR", "error": type(exc).__name__}


def schedule_video_publisher(interval_seconds=120):
    if scheduler.get_job("nexus_video_publisher"):
        return
    scheduler.add_job(
        _run_video_publisher,
        "interval",
        seconds=max(60, int(interval_seconds)),
        id="nexus_video_publisher",
        max_instances=1,
        coalesce=True,
        replace_existing=True
    )


async def _run_video_publication_monitor():
    """Read-only monitoring of pending TikTok and Instagram publications."""
    import asyncio
    try:
        from integrations.video_clipping.video_publisher import (
            monitor_pending_publications
        )
        results = await asyncio.to_thread(monitor_pending_publications)
        counts = {"PUBLISHED": 0, "FAILED": 0, "REVIEW_REQUIRED": 0}
        for item in results or []:
            status = item.get("status", "REVIEW_REQUIRED")
            counts[status] = counts.get(status, 0) + 1
        return {
            "status": "MONITORED",
            "checked": len(results or []),
            "summary": counts,
            "results": results
        }
    except Exception as exc:
        print("[VIDEO PUBLICATION MONITOR]", type(exc).__name__)
        return {"status": "ERROR", "error": type(exc).__name__}


def schedule_video_publication_monitor(interval_seconds=180):
    """Register read-only publication monitoring; never submits uploads."""
    scheduler.add_job(
        _run_video_publication_monitor,
        "interval",
        seconds=max(60, int(interval_seconds)),
        id="nexus_video_publication_monitor",
        max_instances=1,
        coalesce=True,
        replace_existing=True
    )

def start_scheduler():
    initialize()

    if not scheduler.running:
        scheduler.start()

    schedule_mining_autopilot()
    schedule_video_autopilot()
    schedule_video_publisher()
    schedule_video_publication_monitor()

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

# NEXUS Mining Autopilot integration.
MINING_POLICY = Path(__file__).resolve().parent.parent / "config" / "xmrig.policy.json"
MINING_MARKET = Path(__file__).resolve().parent.parent / "config" / "xmrig.market.json"
MINING_HARDWARE = Path(__file__).resolve().parent.parent / "config" / "xmrig.hardware.json"
MINING_JOB_ID = "nexus_mining_autopilot"


async def _run_mining_autopilot():
    """Run the complete multi-coin intelligence cycle under policy control."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    policy_path = root / "config" / "xmrig.policy.json"

    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        if policy.get("mining_enabled") is not True:
            return {"status": "DISABLED"}

        electricity_price = policy.get("electricity_price_per_kwh")
        if electricity_price is None:
            return {"status": "BLOCKED", "reason": "Electricity price not configured"}

        electricity_price = float(electricity_price)
        if electricity_price < 0:
            return {"status": "BLOCKED", "reason": "Invalid electricity price"}

        from integrations.xmrig.mining_intelligence import run_cycle
        result = await asyncio.to_thread(
            run_cycle,
            electricity_price_per_kwh=electricity_price
        )

        return result

    except Exception as exc:
        print(f"[MINING AUTOPILOT] Cycle blocked: {type(exc).__name__}")
        return {"status": "ERROR", "error": type(exc).__name__}
def schedule_mining_autopilot(interval_seconds=300):
    """Register mining evaluation with the existing NEXUS scheduler."""
    interval_seconds = max(60, int(interval_seconds))
    if scheduler.get_job(MINING_JOB_ID):
        scheduler.remove_job(MINING_JOB_ID)

    scheduler.add_job(
        _run_mining_autopilot,
        "interval",
        seconds=interval_seconds,
        id=MINING_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True
    )
