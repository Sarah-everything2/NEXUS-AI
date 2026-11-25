import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from skills.x_growth.draft_manager import get_draft, DRAFT_DIR


PUBLISHED_DIR = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "x_growth"
    / "published"
)


def record_publish_result(draft_id, result, username=None):
    """Record successful, partially successful or failed X publication."""

    if not isinstance(result, dict):
        raise ValueError("Publication result must be a dictionary.")

    draft = get_draft(draft_id)

    if not draft:
        raise ValueError("Draft not found.")

    if draft.get("published"):
        raise ValueError("This draft has already been marked as published.")

    if draft.get("status") not in ("DRAFT", "FAILED"):
        raise ValueError("Only unpublished drafts can be processed.")

    post_ids = []

    if result.get("post_id"):
        post_ids = [str(result["post_id"])]
    else:
        post_ids = [
            str(item)
            for item in (
                result.get("post_ids")
                or result.get("published_ids")
                or []
            )
            if item
        ]

    success = bool(result.get("ok")) and bool(post_ids)

    if success:
        status = "PUBLISHED"
    elif post_ids:
        status = "PARTIAL"
    else:
        status = "FAILED"

    receipt_id = uuid.uuid4().hex
    timestamp = datetime.now(timezone.utc).isoformat()

    links = []
    if username:
        links = [
            f"https://x.com/{username}/status/{post_id}"
            for post_id in post_ids
        ]

    receipt = {
        "receipt_id": receipt_id,
        "draft_id": draft_id,
        "created_at": timestamp,
        "status": status,
        "content_type": draft.get("content_type"),
        "post_ids": post_ids,
        "post_urls": links,
        "username": username,
        "content": draft.get("content"),
        "error": result.get("error"),
        "published": bool(post_ids),
    }

    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)

    receipt_path = PUBLISHED_DIR / f"{receipt_id}.json"
    temporary_path = PUBLISHED_DIR / f".{receipt_id}.tmp"

    try:
        temporary_path.write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary_path.replace(receipt_path)

        draft["status"] = status
        draft["published"] = bool(post_ids)
        draft["publication_receipt_id"] = receipt_id
        draft["published_at"] = timestamp if post_ids else None

        draft_path = DRAFT_DIR / f"{draft_id}.json"
        draft_temp = DRAFT_DIR / f".{draft_id}.tmp"

        try:
            draft_temp.write_text(
                json.dumps(draft, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            draft_temp.replace(draft_path)
        finally:
            if draft_temp.exists():
                draft_temp.unlink()

    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    return receipt


def list_publication_receipts():
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    receipts = []

    for path in PUBLISHED_DIR.glob("*.json"):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(item, dict):
                receipts.append(item)
        except (OSError, json.JSONDecodeError):
            continue

    return sorted(
        receipts,
        key=lambda item: item.get("created_at", ""),
        reverse=True,
    )
