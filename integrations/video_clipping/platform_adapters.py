import os
import json
import inspect
import importlib
import pkgutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "video_platforms.json"
YOUTUBE_DIR = ROOT / "integrations" / "youtube"

TOKEN_ENV = {
    "youtube": ("YOUTUBE_ACCESS_TOKEN", "YOUTUBE_REFRESH_TOKEN"),
    "tiktok": ("TIKTOK_ACCESS_TOKEN",),
    "instagram_reels": ("INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_ACCOUNT_ID")
}


def _config():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def account_readiness(platform):
    config = _config().get("platforms", {}).get(platform, {})
    credentials_present = False
    reason = "Required account credentials are not available"

    if platform == "tiktok":
        try:
            from integrations.tiktok.secure_storage import load_tokens
            tokens = load_tokens() or {}
            credentials_present = bool(tokens.get("access_token"))
            reason = "TikTok OAuth token available" if credentials_present else reason
        except Exception:
            credentials_present = False

    elif platform == "instagram_reels":
        credentials_present = bool(
            os.environ.get("NEXUS_INSTAGRAM_ACCESS_TOKEN")
            and os.environ.get("NEXUS_INSTAGRAM_ACCOUNT_ID")
        )
        reason = "Instagram credentials available" if credentials_present else reason

    elif platform == "youtube":
        required = TOKEN_ENV.get(platform, ())
        credentials_present = bool(required) and all(
            os.environ.get(name) for name in required
        )
        reason = "YouTube credentials available" if credentials_present else reason

    else:
        return {
            "platform": platform,
            "ready": False,
            "reason": "Unsupported platform"
        }

    if not config.get("enabled", False):
        reason = "Platform integration disabled"
    elif not credentials_present:
        reason = "Required account credentials are not available"

    return {
        "platform": platform,
        "ready": bool(config.get("enabled")) and credentials_present,
        "credentials_present": credentials_present,
        "reason": reason
    }

def discover_youtube_uploaders():
    """Discover existing upload functions without executing them."""
    found = []

    if not YOUTUBE_DIR.exists():
        return found

    for path in YOUTUBE_DIR.glob("*.py"):
        if path.name.startswith("_"):
            continue

        module_name = "integrations.youtube." + path.stem

        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue

        for name, function in inspect.getmembers(
            module, inspect.isfunction
        ):
            lowered = name.lower()

            if "upload" not in lowered:
                continue

            try:
                signature = str(inspect.signature(function))
            except (TypeError, ValueError):
                signature = "(signature unavailable)"

            found.append({
                "module": module_name,
                "function": name,
                "signature": signature
            })

    return found


def platform_preflight(platform, video_path, privacy="private"):
    from integrations.video_clipping.video_authorization import authorize_publication
    try:
        authorize_publication(platform, privacy)
    except Exception as exc:
        return {"ready": False, "reason": str(exc)}

    if platform == "instagram_reels" and privacy != "public":
        return {"ready": False, "reason": "Instagram Graph API Reels publishing supports public publishing only."}

    path = Path(video_path)

    if not path.is_file():
        return {"ready": False, "reason": "Video file not found"}

    if path.suffix.lower() not in {".mp4", ".mov", ".mkv"}:
        return {"ready": False, "reason": "Unsupported video format"}

    readiness = account_readiness(platform)

    if not readiness["ready"]:
        return {"ready": False, "reason": readiness["reason"]}

    config = _config().get("platforms", {}).get(platform, {})

    if privacy == "public" and not config.get(
        "autonomous_public", False
    ):
        return {
            "ready": False,
            "reason": "Autonomous public publishing is not authorized"
        }

    if privacy == "private" and not config.get(
        "autonomous_private", False
    ):
        return {
            "ready": False,
            "reason": "Autonomous private publishing is not enabled"
        }

    from integrations.video_clipping.platform_preflight import preflight_publication

    shared_check = preflight_publication(
        platform, video_path=video_path, check_account=False
    )
    if not shared_check.get("ready"):
        return {
            "ready": False,
            "reason": "; ".join(shared_check.get("errors", ["Shared media preflight failed"]))
        }

    return {
        "ready": True,
        "platform": platform,
        "privacy": privacy,
        "file_size": path.stat().st_size
    }



def publish(platform, video_path, metadata, privacy="private"):
    check = platform_preflight(platform, video_path, privacy)

    if not check["ready"]:
        return {"status": "REVIEW_REQUIRED", "reason": check["reason"]}

    if platform in {"youtube", "youtube_shorts"}:
        from integrations.youtube import tools as youtube_tools

        metadata = metadata or {}

        kwargs = {
            "video_path": str(video_path),
            "title": str(metadata.get("title", Path(video_path).stem))[:100],
            "description": str(metadata.get("description", ""))[:5000],
            "tags": metadata.get("tags", []),
            "category_id": str(metadata.get("category_id", "22")),
            "privacy_status": privacy,
            "made_for_kids": metadata.get("made_for_kids")
        }

        if not isinstance(kwargs["made_for_kids"], bool):
            return {
                "status": "REVIEW_REQUIRED",
                "reason": "Explicit made_for_kids classification required"
            }

        try:
            uploader = youtube_tools.youtube_upload_autonomous

            result = uploader(**kwargs)

            if isinstance(result, dict):
                if result.get("success") is False or result.get("error"):
                    return {
                        "status": "FAILED",
                        "reason": str(result.get("error", "Upload failed"))[:300]
                    }

                video_id = (
                    result.get("video_id")
                    or result.get("id")
                )

                if not video_id and result.get("success") is not True:
                    return {
                        "status": "REVIEW_REQUIRED",
                        "reason": "Uploader returned no verifiable publication ID",
                        "result": result
                    }

                return {
                    "status": "PUBLISHED",
                    "result": {
                        "video_id": video_id,
                        "url": result.get("url"),
                        "raw_status": result.get("status")
                    }
                }

            return {
                "status": "REVIEW_REQUIRED",
                "reason": "Uploader returned an unrecognized result",
                "result_type": type(result).__name__
            }

        except Exception as exc:
            return {
                "status": "REVIEW_REQUIRED",
                "reason": type(exc).__name__
            }

    metadata = metadata or {}

    if platform == "tiktok":
        try:
            from integrations.tiktok.client import NexusTikTokClient
            client = NexusTikTokClient()
            if privacy not in ("private", "public"):
                return {"status": "REVIEW_REQUIRED", "reason": "TikTok supports private or public visibility only"}
            privacy_level = "SELF_ONLY" if privacy == "private" else "PUBLIC_TO_EVERYONE"
            result = client.publish_video(
                video_path=str(video_path),
                title=str(metadata.get("title", Path(video_path).stem))[:150],
                privacy_level=privacy_level,
                consent=True,
                disable_comment=bool(metadata.get("disable_comment", False)),
                disable_duet=bool(metadata.get("disable_duet", False)),
                disable_stitch=bool(metadata.get("disable_stitch", False))
            )
            return {
                "status": "REVIEW_REQUIRED",
                "reason": "TikTok submission is processing; verify publication status before any retry",
                "result": {
                    "publish_id": result.get("publish_id"),
                    "processing_status": result.get("status")
                }
            }
        except Exception as exc:
            return {"status": "REVIEW_REQUIRED", "reason": type(exc).__name__}

    if platform == "instagram_reels":
        video_url = metadata.get("video_url")
        if not isinstance(video_url, str) or not video_url.startswith("https://"):
            return {"status": "REVIEW_REQUIRED", "reason": "Instagram requires metadata.video_url with a public HTTPS video URL"}
        try:
            from integrations.instagram.reels_publisher import create_reel, reel_status, publish_reel
            created = create_reel(
                video_url=video_url,
                caption=str(metadata.get("description", metadata.get("caption", "")))[:2200],
                consent=True
            )
            container_id = created.get("id") if isinstance(created, dict) else None
            if not container_id:
                return {"status": "REVIEW_REQUIRED", "reason": "Instagram returned no verifiable container ID"}
            status_result = reel_status(container_id)
            if status_result.get("status_code") != "FINISHED":
                return {
                    "status": "REVIEW_REQUIRED",
                    "reason": "Instagram Reel container is not ready; manual status verification required",
                    "result": {"container_id": container_id, "container_status": status_result.get("status_code")}
                }
            published = publish_reel(container_id, consent=True)
            media_id = published.get("id") if isinstance(published, dict) else None
            if not media_id:
                return {
                    "status": "REVIEW_REQUIRED",
                    "reason": "Instagram publish response has no verifiable media ID; do not retry automatically",
                    "result": {"container_id": container_id}
                }
            return {"status": "PUBLISHED", "result": {"media_id": media_id, "container_id": container_id}}
        except Exception as exc:
            return {"status": "REVIEW_REQUIRED", "reason": type(exc).__name__}

    return {"status": "REVIEW_REQUIRED", "reason": "Unsupported platform"}
