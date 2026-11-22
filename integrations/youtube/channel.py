"""Read-only YouTube channel information."""
from integrations.youtube.oauth import get_youtube_service


def get_my_channel():
    youtube = get_youtube_service()
    response = youtube.channels().list(
        part="snippet,statistics",
        mine=True
    ).execute()

    channels = response.get("items", [])
    if not channels:
        return {"connected": False, "error": "No channel found"}

    channel = channels[0]
    snippet = channel.get("snippet", {})
    stats = channel.get("statistics", {})

    return {
        "connected": True,
        "channel_id": channel.get("id"),
        "channel_name": snippet.get("title"),
        "subscribers": stats.get("subscriberCount"),
        "views": stats.get("viewCount"),
        "videos": stats.get("videoCount"),
    }
