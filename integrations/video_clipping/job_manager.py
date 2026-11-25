import json
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INBOX = ROOT / "workspace" / "video_inbox"
OUTPUT = ROOT / "workspace" / "video_output"
QUEUE = ROOT / "config" / "video_jobs.json"

INBOX.mkdir(parents=True, exist_ok=True)
OUTPUT.mkdir(parents=True, exist_ok=True)


def _read():
    try:
        data = json.loads(QUEUE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save(jobs):
    temp = QUEUE.with_suffix(".tmp")
    temp.write_text(json.dumps(jobs, indent=2), encoding="utf-8")
    temp.replace(QUEUE)


def submit_video(filename, priority=5):
    source = (INBOX / filename).resolve()

    if source.parent != INBOX.resolve():
        raise ValueError("Video must be inside the video inbox")

    if not source.is_file():
        raise FileNotFoundError(str(source))

    if source.suffix.lower() not in {
        ".mp4", ".mov", ".mkv", ".avi", ".webm"
    }:
        raise ValueError("Unsupported video format")

    jobs = _read()

    for job in jobs:
        if (
            job.get("source") == str(source)
            and job.get("status") in {"QUEUED", "PROCESSING"}
        ):
            return {"status": "ALREADY_QUEUED", "job_id": job["id"]}

    now = time.time()
    job = {
        "id": uuid.uuid4().hex,
        "source": str(source),
        "priority": max(1, min(int(priority), 10)),
        "status": "QUEUED",
        "attempts": 0,
        "created_at": now,
        "updated_at": now
    }

    jobs.append(job)
    _save(jobs)
    return {"status": "QUEUED", "job_id": job["id"]}


def next_job():
    pending = [
        j for j in _read()
        if j.get("status") == "QUEUED"
        and int(j.get("attempts", 0)) < 3
    ]
    pending.sort(
        key=lambda j: (-int(j.get("priority", 5)), j["created_at"])
    )
    return pending[0] if pending else None


def update_job(job_id, status, error=None):
    if status not in {"PROCESSING", "COMPLETED", "FAILED", "QUEUED"}:
        raise ValueError("Invalid status")

    jobs = _read()

    for job in jobs:
        if job["id"] != job_id:
            continue

        now = time.time()
        job["updated_at"] = now

        if status == "PROCESSING":
            job["attempts"] = int(job.get("attempts", 0)) + 1
            job["started_at"] = now

        if error:
            job["last_error"] = str(error)[:300]

        if status == "FAILED" and job.get("attempts", 0) < 3:
            job["status"] = "QUEUED"
        else:
            job["status"] = status

        _save(jobs)
        return job

    raise KeyError("Unknown job ID")


def list_jobs():
    return sorted(
        _read(),
        key=lambda j: j.get("created_at", 0),
        reverse=True
    )


def recover_stale_jobs(max_age_seconds=3600):
    jobs = _read()
    recovered = 0
    now = time.time()

    for job in jobs:
        if job.get("status") != "PROCESSING":
            continue

        if now - float(job.get("updated_at", 0)) < max_age_seconds:
            continue

        job["status"] = (
            "QUEUED" if int(job.get("attempts", 0)) < 3 else "FAILED"
        )
        job["updated_at"] = now
        job["last_error"] = "Recovered interrupted processing job"
        recovered += 1

    if recovered:
        _save(jobs)

    return recovered
