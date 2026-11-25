import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


DRAFT_DIR = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "x_growth"
    / "drafts"
)


def save_draft(content, content_type="post", research=None):
    if content_type not in ("post", "thread"):
        raise ValueError("Content type must be post or thread.")

    if content_type == "post":
        if not isinstance(content, str) or not content.strip() or len(content) > 280:
            raise ValueError("Invalid X post.")
        content = content.strip()

    elif content_type == "thread":
        if not isinstance(content, list) or not 2 <= len(content) <= 10:
            raise ValueError("Thread must contain 2-10 posts.")

        if any(
            not isinstance(post, str)
            or not post.strip()
            or len(post.strip()) > 280
            for post in content
        ):
            raise ValueError("Thread contains an invalid post.")

        content = [post.strip() for post in content]

    DRAFT_DIR.mkdir(parents=True, exist_ok=True)

    draft_id = uuid.uuid4().hex
    timestamp = datetime.now(timezone.utc).isoformat()

    draft = {
        "draft_id": draft_id,
        "created_at": timestamp,
        "content_type": content_type,
        "content": content,
        "research": research or {},
        "status": "DRAFT",
        "published": False,
    }

    path = DRAFT_DIR / f"{draft_id}.json"
    temporary_path = DRAFT_DIR / f".{draft_id}.tmp"

    try:
        temporary_path.write_text(
            json.dumps(draft, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    return draft


def list_drafts():
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    drafts = []

    for path in DRAFT_DIR.glob("*.json"):
        try:
            draft = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(draft, dict):
                drafts.append(draft)
        except (OSError, json.JSONDecodeError):
            continue

    return sorted(
        drafts,
        key=lambda item: item.get("created_at", ""),
        reverse=True,
    )


def get_draft(draft_id):
    if not isinstance(draft_id, str) or not draft_id.isalnum():
        return None

    path = DRAFT_DIR / f"{draft_id}.json"

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
