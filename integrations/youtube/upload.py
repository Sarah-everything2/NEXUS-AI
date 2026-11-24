"""Safety-controlled YouTube upload engine."""
import json
from pathlib import Path
from integrations.youtube.oauth import get_youtube_service
from integrations.youtube.upload_limiter import can_upload, record_upload

CONFIG_PATH = Path(__file__).with_name("config.json")


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def upload_video(
    video_path,
    title,
    description="",
    tags=None,
    category_id="22",
    privacy_status=None,
    approved=False,
    made_for_kids=None,
):
    if not isinstance(made_for_kids, bool):
        raise ValueError("Explicit made_for_kids True/False declaration required.")

    config = load_config()

    if not config.get("enabled") or not config.get("publishing_enabled"):
        raise PermissionError("YouTube publishing is disabled.")
    limit = int(config.get("max_uploads_per_day", 3))
    if not can_upload(limit):
        raise PermissionError("Daily upload limit reached.")

    if config.get("require_human_approval", True) and not approved:
        raise PermissionError("Human approval required.")

    path = Path(video_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError("Video file not found.")

    max_size = config.get("max_video_size_mb", 512) * 1024 * 1024
    if path.stat().st_size > max_size:
        raise ValueError("Video exceeds configured size limit.")

    allowed_extensions = config.get("allowed_video_extensions", [".mp4"])
    if path.suffix.lower() not in allowed_extensions:
        raise ValueError("Unsupported video format.")

    privacy_status = privacy_status or config.get("default_privacy", "private")

    if privacy_status not in ("private", "unlisted", "public"):
        raise ValueError("Invalid privacy setting.")

    if privacy_status == "public" and not config.get("allow_public_publish", False):
        raise PermissionError("Public publishing is disabled.")

    youtube = get_youtube_service()

    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags or [],
            "categoryId": str(category_id),
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(
            str(path), chunksize=8 * 1024 * 1024, resumable=True
        ),
    )

    result = request.execute()
    record_upload(limit)

    return {
        "uploaded": True,
        "video_id": result.get("id"),
        "privacy_status": privacy_status,
    }



def upload_video_autonomous(**kwargs):
    """Restricted autonomous uploads: private videos only."""
    from core.settings import load_settings

    settings = load_settings()
    config = load_config()

    if not settings.get("autonomous_mode", False):
        raise PermissionError("NEXUS autonomous mode is disabled.")

    if not config.get("allow_autonomous_private_uploads", False):
        raise PermissionError("Autonomous private uploads are not authorized in config.")

    if "made_for_kids" not in kwargs or not isinstance(kwargs["made_for_kids"], bool):
        raise ValueError("Explicit made_for_kids declaration required.")

    kwargs.pop("approved", None)
    kwargs.pop("privacy_status", None)

    return upload_video(
        **kwargs,
        privacy_status="private",
        approved=True,
    )
