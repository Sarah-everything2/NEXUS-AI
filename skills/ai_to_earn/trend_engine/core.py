"""NEXUS AI-to-Earn Trend Discovery Engine."""
import re
from datetime import datetime, timezone

PLATFORMS = ("youtube", "x", "tiktok")

def normalize_text(text):
    return re.sub(r"\s+", " ", (text or "").strip()).lower()

def score_trend(item):
    """Rank trends using recency, engagement, and cross-platform presence."""
    views = max(0, int(item.get("views", 0) or 0))
    likes = max(0, int(item.get("likes", 0) or 0))
    shares = max(0, int(item.get("shares", 0) or 0))
    platforms = len(set(item.get("platforms", []) or []))
    age_hours = max(0.0, float(item.get("age_hours", 72) or 72))

    engagement = min(30, (likes + shares * 2) / max(views, 1) * 3000)
    freshness = max(0, 25 * (1 - min(age_hours, 72) / 72))
    reach = min(20, views / 10000)
    cross_platform = min(25, platforms * 8)

    return round(min(100, freshness + engagement + reach + cross_platform), 2)

def rank_trends(items):
    for item in items:
        item["trend_score"] = score_trend(item)
    return sorted(items, key=lambda x: x["trend_score"], reverse=True)
