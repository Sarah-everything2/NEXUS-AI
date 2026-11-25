import os
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]

def _load_json(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}

def _credential_state(names):
    present = [name for name in names if os.getenv(name)]
    return {
        "credentials_configured": bool(present),
        "missing": [name for name in names if not os.getenv(name)]
    }

def platform_readiness():
    config = _load_json(ROOT / "config" / "video_platforms.json")
    results = {}

    youtube = _load_json(ROOT / "config" / "youtube.json")
    yt_creds = _credential_state([
        "NEXUS_YOUTUBE_CLIENT_ID",
        "NEXUS_YOUTUBE_CLIENT_SECRET"
    ])
    results["youtube"] = {
        "credentials": yt_creds,
        "configuration_present": bool(youtube),
        "publishing_enabled": bool(
            youtube.get("publishing_enabled", False)
        ),
        "ready": yt_creds["credentials_configured"] and bool(youtube)
    }

    tt_creds = _credential_state(["NEXUS_TIKTOK_ACCESS_TOKEN"])
    results["tiktok"] = {
        "credentials": tt_creds,
        "configuration_present": bool(config.get("tiktok")),
        "ready": tt_creds["credentials_configured"]
    }

    ig_creds = _credential_state([
        "NEXUS_INSTAGRAM_ACCESS_TOKEN",
        "NEXUS_INSTAGRAM_ACCOUNT_ID"
    ])
    results["instagram"] = {
        "credentials": ig_creds,
        "configuration_present": bool(config.get("instagram")),
        "ready": ig_creds["credentials_configured"]
    }

    for name, result in results.items():
        result["status"] = "CONFIGURED" if result["ready"] else "SETUP_REQUIRED"

    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "mode": "READINESS_CHECK_ONLY",
        "platforms": results,
        "publishing_performed": False
    }

def print_platform_readiness():
    result = platform_readiness()
    print("NEXUS VIDEO PLATFORM READINESS")
    print("=" * 42)
    for name, data in result["platforms"].items():
        print(f"{name.upper():12} {data['status']}")
        for key in data["credentials"]["missing"]:
            print(f"  Missing environment variable: {key}")
    print("=" * 42)
    print("SAFE: No credentials displayed. No uploads performed.")
    return result

def preflight_publication(platform, video_path=None, video_url=None, check_account=True):
    """Unified fail-closed gate before a video publication is attempted."""
    platform = str(platform).lower()
    readiness = platform_readiness()
    aliases = {"youtube_shorts": "youtube", "instagram_reels": "instagram"}
    platform = aliases.get(platform, platform)
    account = readiness["platforms"].get(platform)

    result = {
        "platform": platform,
        "ready": False,
        "checks": {},
        "errors": [],
        "publishing_performed": False,
    }

    if account is None:
        result["errors"].append("Unsupported publishing platform.")
        return result

    result["checks"]["account"] = account
    if check_account and not account.get("ready"):
        result["errors"].append("Platform account setup is incomplete.")

    try:
        if platform == "instagram" and video_url:
            if not video_url:
                result["errors"].append("Instagram requires a public video URL.")
            else:
                from integrations.instagram.reels_publisher import validate_remote_video_url
                result["checks"]["media"] = validate_remote_video_url(video_url)
        else:
            if not video_path:
                result["errors"].append("A local video file is required.")
            else:
                from integrations.video_clipping.media_preflight import validate_for_platform
                media = validate_for_platform(video_path, platform)
                result["checks"]["media"] = media
                if not media.get("valid"):
                    result["errors"].extend(media.get("errors", ["Media validation failed."]))
    except Exception as exc:
        result["errors"].append(f"Preflight failed: {type(exc).__name__}: {exc}")

    result["ready"] = not result["errors"]
    return result
