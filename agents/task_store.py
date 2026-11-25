import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

TASK_FILE = Path(__file__).resolve().parents[1] / "data" / "signal_commander" / "agent_tasks.json"
VALID_STATUSES = {"PREPARED", "IN_PROGRESS", "COMPLETED", "FAILED", "CANCELLED"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load():
    TASK_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not TASK_FILE.exists():
        return {"tasks": {}}
    try:
        data = json.loads(TASK_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("tasks"), dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"tasks": {}}


def _save(data):
    TASK_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = TASK_FILE.with_suffix(".tmp")
    temp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temp.replace(TASK_FILE)


def _task_id(task):
    opportunity = task.get("opportunity", {})
    identity = (
        str(opportunity.get("source", "")).strip().lower()
        or str(opportunity.get("title", "")).strip().lower()
    )
    if not identity:
        raise ValueError("Task requires an opportunity title or source.")
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def save_tasks(tasks):
    if not isinstance(tasks, (list, tuple)):
        raise ValueError("Tasks must be a list.")

    data = _load()
    saved = []

    for task in tasks:
        if not isinstance(task, dict):
            continue

        task_id = _task_id(task)
        now = _now()
        existing = data["tasks"].get(task_id)

        if existing:
            existing["last_seen"] = now
            existing["discovery_count"] = existing.get("discovery_count", 1) + 1
            saved.append(existing)
            continue

        record = dict(task)
        record.update({
            "task_id": task_id,
            "status": "PREPARED",
            "created_at": now,
            "updated_at": now,
            "last_seen": now,
            "discovery_count": 1,
            "execution_started": False,
        })
        data["tasks"][task_id] = record
        saved.append(record)

    _save(data)
    return {"status": "SAVED", "tasks_saved": len(saved), "tasks": saved}


def get_tasks(status=None, limit=100):
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000.")
    if status is not None and status not in VALID_STATUSES:
        raise ValueError("Invalid task status.")

    tasks = list(_load()["tasks"].values())
    if status:
        tasks = [task for task in tasks if task.get("status") == status]

    tasks.sort(key=lambda task: task.get("updated_at", ""), reverse=True)
    return {"status": "SUCCESS", "count": len(tasks[:limit]), "tasks": tasks[:limit]}


def update_task(task_id, status):
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("A task ID is required.")
    if status not in VALID_STATUSES:
        raise ValueError("Invalid task status.")

    data = _load()
    task = data["tasks"].get(task_id)
    if not task:
        return {"status": "NOT_FOUND", "task_id": task_id}

    task["status"] = status
    task["updated_at"] = _now()
    _save(data)

    return {"status": "UPDATED", "task": task}
