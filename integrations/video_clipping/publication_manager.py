import json
import time
import uuid
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "config" / "video_publication_queue.json"
HISTORY = ROOT / "workspace" / "video_output" / "publication_history.jsonl"

PLATFORMS = {
    "youtube_shorts",
    "youtube",
    "tiktok",
    "instagram_reels"
}


def _read():
    try:
        data = json.loads(QUEUE.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save(jobs):
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    temp = QUEUE.with_suffix(".tmp")
    temp.write_text(json.dumps(jobs, indent=2), encoding="utf-8")
    temp.replace(QUEUE)


def _fingerprint(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def enqueue(video_path, platform, metadata, privacy="private",
            scheduled_at=None):
    path = Path(video_path).resolve()

    if platform not in PLATFORMS:
        raise ValueError("Unsupported publishing platform")

    if not path.is_file():
        raise FileNotFoundError(str(path))

    if path.suffix.lower() not in {".mp4", ".mov", ".mkv"}:
        raise ValueError("Unsupported publishing format")

    fingerprint = _fingerprint(path)
    jobs = _read()

    for job in jobs:
        if (
            job.get("fingerprint") == fingerprint
            and job.get("platform") == platform
            and job.get("status") in {
                "QUEUED", "PUBLISHING", "PUBLISHED"
            }
        ):
            return {
                "status": "DUPLICATE",
                "job_id": job["id"]
            }

    if privacy not in {"private", "unlisted", "public"}:
        raise ValueError("Invalid privacy setting")

    now = time.time()

    job = {
        "id": uuid.uuid4().hex,
        "video_path": str(path),
        "fingerprint": fingerprint,
        "platform": platform,
        "privacy": privacy,
        "metadata": metadata or {},
        "scheduled_at": scheduled_at,
        "status": "QUEUED",
        "attempts": 0,
        "created_at": now,
        "updated_at": now,
        "external_id": None
    }

    jobs.append(job)
    _save(jobs)

    return {"status": "QUEUED", "job_id": job["id"]}


def list_publications():
    return sorted(
        _read(),
        key=lambda item: item.get("created_at", 0),
        reverse=True
    )


def update_publication(job_id, status, result=None, error=None):
    allowed = {
        "QUEUED", "PUBLISHING", "PUBLISHED",
        "FAILED", "REVIEW_REQUIRED"
    }

    if status not in allowed:
        raise ValueError("Invalid publication status")

    jobs = _read()

    for job in jobs:
        if job["id"] != job_id:
            continue

        job["status"] = status
        job["updated_at"] = time.time()

        if result:
            job["external_id"] = result.get("video_id")
            job["external_url"] = result.get("url")

        if error:
            job["last_error"] = str(error)[:300]

        _save(jobs)

        HISTORY.parent.mkdir(parents=True, exist_ok=True)
        with HISTORY.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({
                "job_id": job_id,
                "status": status,
                "timestamp": time.time(),
                "error": str(error)[:300] if error else None
            }) + "\n")

        return job

    raise KeyError("Publication job not found")


def get_ready_jobs():
    now = time.time()

    return [
        job for job in list_publications()
        if job.get("status") == "QUEUED"
        and (
            job.get("scheduled_at") is None
            or float(job["scheduled_at"]) <= now
        )
    ]


def recover_interrupted():
    jobs = _read()
    count = 0

    for job in jobs:
        if job.get("status") != "PUBLISHING":
            continue

        # An interrupted network upload may already have reached
        # the platform. Never blindly retry an uncertain upload.
        job["status"] = "REVIEW_REQUIRED"
        job["last_error"] = (
            "Interrupted upload; reconcile remote platform state first"
        )
        job["updated_at"] = time.time()
        count += 1

    if count:
        _save(jobs)

    return count
