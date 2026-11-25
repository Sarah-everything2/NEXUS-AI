"""Independent authorization policy for autonomous video publishing."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "config" / "video_autopilot.policy.json"
EMERGENCY_STOP = ROOT / "config" / "VIDEO_EMERGENCY_STOP"

def load_policy():
    if EMERGENCY_STOP.exists():
        raise PermissionError("Video publishing emergency stop is active.")
    if not POLICY.is_file():
        raise PermissionError("Video publishing policy is missing.")
    try:
        data = json.loads(POLICY.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise PermissionError("Video publishing policy is invalid.") from exc
    if not isinstance(data, dict):
        raise PermissionError("Video publishing policy is invalid.")
    return data

def authorize_publication(platform, privacy="private"):
    policy = load_policy()
    if policy.get("enabled") is not True or policy.get("auto_publish_enabled") is not True:
        raise PermissionError("Autonomous video publishing is disabled.")
    if privacy not in ("private", "public"):
        raise PermissionError("Unsupported publication visibility.")
    if privacy == "public" and policy.get("allow_public_upload") is not True:
        raise PermissionError("Public video publishing is not authorized.")
    if privacy == "private" and policy.get("allow_private_upload") is not True:
        raise PermissionError("Private video publishing is not authorized.")
    key = "youtube" if platform == "youtube_shorts" else platform
    platforms = policy.get("platforms")
    if not isinstance(platforms, dict):
        raise PermissionError("Per-platform video authorization is missing.")
    section = platforms.get(key)
    if not isinstance(section, dict) or section.get("enabled") is not True:
        raise PermissionError("Video platform is not authorized.")
    flag = "autonomous_public" if privacy == "public" else "autonomous_private"
    if section.get(flag) is not True:
        raise PermissionError(f"{platform} {privacy} publishing is not authorized.")
    return {"authorized": True, "platform": key, "privacy": privacy}
