"""NEXUS AI-to-Earn Winning Story Selector. Production mode."""
import json
import subprocess
import sys
from datetime import datetime, timezone

from .youtube import search_youtube
from .core import rank_trends

TESTING_MODE = False

NICHES = {
    "AI Agents for Business": "AI agents business automation",
    "No-Code AI Automation": "n8n AI automation workflows",
    "AI Tools for Business": "AI tools save businesses time money"
}

def get_full_metadata(url):
    try:
        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp",
             "--skip-download", "--dump-single-json",
             "--no-warnings", "--no-call-home", url],
            capture_output=True, text=True,
            timeout=35, check=False,
            encoding="utf-8", errors="replace"
        )
        if result.returncode != 0:
            return {}
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return {}

def discover_winning_stories(per_niche=2):
    candidates = {}
    for niche, query in NICHES.items():
        for video in search_youtube(query, per_niche):
            video["niche"] = niche
            candidates[video["video_id"]] = video

    enriched = []
    now = datetime.now(timezone.utc)

    for video in candidates.values():
        meta = get_full_metadata(video["url"])
        if not meta:
            continue

        video["views"] = meta.get("view_count") or video.get("views") or 0
        video["likes"] = meta.get("like_count") or 0
        video["channel"] = meta.get("channel") or video.get("channel", "")
        video["upload_date"] = meta.get("upload_date")
        video["duration"] = meta.get("duration")
        video["platforms"] = ["youtube"]
        video["shares"] = 0

        age_hours = 72
        published = video.get("upload_date")
        if published:
            try:
                date = datetime.strptime(published, "%Y%m%d").replace(tzinfo=timezone.utc)
                age_hours = max(0, (now - date).total_seconds() / 3600)
            except ValueError:
                pass

        video["age_hours"] = age_hours
        video["like_ratio"] = round(
            video["likes"] / max(video["views"], 1) * 100, 3
        )
        video["trend_score"] = 0
        enriched.append(video)

    ranked = rank_trends(enriched)
    for item in ranked:
        item["story_opportunity"] = round(
            item["trend_score"] * 0.8 +
            min(item["like_ratio"] * 10, 20), 2
        )

    return sorted(
        ranked,
        key=lambda x: x["story_opportunity"],
        reverse=True
    )
