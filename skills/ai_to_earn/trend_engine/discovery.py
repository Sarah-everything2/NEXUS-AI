"""NEXUS AI-to-Earn YouTube discovery pipeline. TESTING ONLY."""
from datetime import datetime, timezone
from .youtube import search_youtube
from .core import rank_trends

TESTING_MODE = True

def discover_youtube_trends(query, limit=5):
    videos = search_youtube(query, limit)
    now = datetime.now(timezone.utc)

    for item in videos:
        upload = item.get("upload_date")
        age_hours = 72
        if upload and len(upload) == 8:
            try:
                published = datetime.strptime(upload, "%Y%m%d").replace(tzinfo=timezone.utc)
                age_hours = max(0, (now - published).total_seconds() / 3600)
            except ValueError:
                pass

        item.update({
            "platforms": ["youtube"],
            "age_hours": age_hours,
            "likes": 0,
            "shares": 0
        })

    return rank_trends(videos)
