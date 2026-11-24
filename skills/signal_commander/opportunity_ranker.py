"""Evidence-based NEXUS opportunity scoring."""

from datetime import datetime, timezone
from urllib.parse import urlparse
import math
import re
from skills.signal_commander.discovery_memory import get_discovery_memory


NICHE_KEYWORDS = {
    "mining": ["mining", "minerals", "gold", "copper", "lithium", "uranium", "metals"],
    "politics": ["politics", "government", "election", "policy", "parliament", "president"],
    "artificial intelligence": ["artificial intelligence", "AI", "machine learning", "LLM", "robotics"],
    "technology": ["technology", "tech", "software", "innovation", "digital"],
    "crypto": ["crypto", "cryptocurrency", "bitcoin", "blockchain", "ethereum"],
    "finance": ["finance", "stocks", "markets", "investing", "economy"],
    "engineering": ["engineering", "infrastructure", "construction", "manufacturing"],
    "football": ["football", "soccer", "FIFA", "Premier League"],
    "basketball": ["basketball", "NBA", "WNBA"],
}

TRUSTED_SOURCES = {
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk",
    "npr.org", "ft.com", "bloomberg.com", "theguardian.com",
    "nature.com", "sciencedaily.com", "investingnews.com",
}


def _recency_score(published_at=None):
    if not published_at:
        return 0.20

    try:
        value = str(published_at).replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        if (dt - datetime.now(timezone.utc)).total_seconds() > 86400:
            return 0.0

        age = max(
            0,
            (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        )

        if age <= 24:
            return 1.0
        if age <= 72:
            return 0.85
        if age <= 168:
            return 0.65
        if age <= 720:
            return 0.40
        return 0.10

    except (ValueError, TypeError, OverflowError):
        return 0.20


def _source_score(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            return 0.10
        domain = parsed.hostname.lower()
        domain = domain.removeprefix("www.")

        if not domain:
            return 0.10

        if any(domain == d or domain.endswith("." + d) for d in TRUSTED_SOURCES):
            return 1.0

        if domain.endswith((".gov", ".edu")):
            return 0.95

        return 0.55

    except (ValueError, TypeError):
        return 0.10


def _relevance_score(text, niche):
    text = text.lower()
    niche_lower = niche.lower().strip()

    keywords = NICHE_KEYWORDS.get(
        niche_lower,
        [niche_lower]
    )

    matches = sum(
        1 for keyword in keywords
        if (re.search(r"\b" + re.escape(keyword.lower()) + r"\b", text) if len(keyword) <= 3 else keyword.lower() in text)
    )

    if not keywords:
        return 0.30

    return min(1.0, matches / min(3, len(keywords)))


def score_opportunity(item, niche="", repeat_count=1):
    title = (item.get("title") or "").strip()
    description = (
        item.get("body") or item.get("description") or ""
    ).strip()
    url = (item.get("href") or item.get("url") or "").strip()

    text = f"{title} {description}"

    relevance = _relevance_score(text, niche)

    evidence = (
        0.30 * bool(title)
        + 0.30 * bool(description)
        + 0.25 * url.startswith("http")
        + 0.15 * bool(item.get("published") or item.get("date"))
    )

    recency = _recency_score(
        item.get("published")
        or item.get("date")
        or item.get("published_at")
    )

    source_quality = _source_score(url)

    momentum = min(
        1.0,
        math.log1p(max(1, repeat_count)) / math.log(6)
    )

    score = (
        recency * 0.30
        + relevance * 0.30
        + evidence * 0.15
        + source_quality * 0.15
        + momentum * 0.10
    ) * 100

    return {
        "title": title,
        "url": url,
        "niche": niche,
        "score": round(score, 2),
        "recency_score": round(recency, 3),
        "relevance_score": round(relevance, 3),
        "evidence_score": round(evidence, 3),
        "source_quality_score": round(source_quality, 3),
        "momentum_score": round(momentum, 3),
        "confidence": (
            "HIGH" if evidence >= 0.85 and source_quality >= 0.8
            else "MEDIUM" if evidence >= 0.60
            else "LOW"
        ),
        "scoring_note": (
            "Estimated discovery opportunity, not verified audience demand."
        ),
    }


def rank_opportunities(items, niche="", repeat_counts=None):
    repeat_counts = repeat_counts or {}
    memory_counts = {str(r.get('name', '')).strip().lower(): r.get('discovery_count', 1) for r in get_discovery_memory().get('trends', []) if isinstance(r, dict)}
    scored = []

    for item in items:
        identity = (
            item.get("href")
            or item.get("url")
            or item.get("title")
            or ""
        ).strip().lower()

        memory_count = memory_counts.get((item.get('title') or '').strip().lower(), 1)
        count = max(1, int(repeat_counts.get(identity, 1)), int(memory_count))

        scored.append(
            score_opportunity(item, niche, repeat_count=count)
        )

    return sorted(
        scored,
        key=lambda item: (
            item["score"],
            item["relevance_score"],
            item["source_quality_score"],
            item["recency_score"],
            item["title"].lower(),
        ),
        reverse=True,
    )
