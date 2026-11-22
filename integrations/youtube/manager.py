"""Central YouTube management interface for NEXUS AI."""
from integrations.youtube.secure_storage import token_status
from integrations.youtube.channel import get_my_channel
from integrations.youtube.upload import load_config


def status():
    return {
        "platform": "YouTube",
        "connection": token_status(),
        "publishing_enabled": load_config().get("publishing_enabled", False),
        "approval_required": load_config().get("require_human_approval", True),
        "default_privacy": load_config().get("default_privacy", "private"),
    }


def channel():
    if not token_status()["connected"]:
        return {"connected": False, "message": "YouTube account not connected"}
    return get_my_channel()


def publishing_controls():
    config = load_config()
    return {
        "enabled": config.get("enabled", False),
        "publishing_enabled": config.get("publishing_enabled", False),
        "public_publish_allowed": config.get("allow_public_publish", False),
        "approval_required": config.get("require_human_approval", True),
        "default_privacy": config.get("default_privacy", "private"),
        "daily_limit": config.get("max_uploads_per_day", 3),
    }
