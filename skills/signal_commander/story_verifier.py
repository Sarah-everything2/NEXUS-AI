"""Evidence-based corroboration for Signal Commander stories.

Search-result corroboration is not proof of truth. This module reports
independent publisher matches and leaves final factual judgment to review.
"""
import re
from urllib.parse import urlparse

from tools.trend_discovery import discover_trends

TRUSTED_DOMAINS = {
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "npr.org",
    "ft.com", "bloomberg.com", "theguardian.com", "nature.com",
    "sciencedaily.com", "investingnews.com",
}


def _domain(url):
    try:
        host = (urlparse(url or "").hostname or "").lower()
        host = host.removeprefix("www.")
        return "" if host in {"news.google.com", "google.com"} else host
    except (TypeError, ValueError):
        return ""


def _tokens(value):
    return {
        word for word in re.findall(r"[a-z0-9]{3,}", (value or "").lower())
        if word not in {"the", "and", "for", "with", "from", "that", "this"}
    }


def _similarity(left, right):
    a, b = _tokens(left), _tokens(right)
    return len(a & b) / len(a | b) if a and b else 0.0


async def verify_story(story, max_results=10):
    """Find independent reports that substantially match a discovered story."""
    title = (story.get("title") or "").strip()
    url = (story.get("href") or story.get("url") or "").strip()
    if not title:
        return {
            "verification_status": "UNVERIFIED",
            "verification_score": 0,
            "independent_sources": 0,
            "source_domains": [],
            "matching_evidence": [],
            "verification_notes": ["Story has no title to verify."],
        }

    query = f'"{title[:180]}"'
    try:
        result = await discover_trends(
            query=query, max_results=max(3, min(int(max_results), 20)),
            timelimit="m",
        )
    except Exception as exc:
        result = {"status": "ERROR", "results": [], "error": str(exc)[:160]}

    original_domain = _domain(url)
    matches = []
    domains = set()
    for item in result.get("results", []):
        candidate_title = item.get("title") or ""
        candidate_url = item.get("href") or item.get("url") or ""
        domain = _domain(candidate_url)
        similarity = _similarity(title, candidate_title)
        shared = len(_tokens(title) & _tokens(candidate_title))
        if not domain or not candidate_url.startswith(("http://", "https://")):
            continue
        if domain == original_domain or shared < 3 or similarity < 0.45:
            continue
        if domain in domains:
            continue
        domains.add(domain)
        matches.append({
            "title": candidate_title,
            "url": candidate_url,
            "domain": domain,
            "title_similarity": round(similarity, 3),
            "source_quality": "ESTABLISHED" if any(
                domain == trusted or domain.endswith("." + trusted)
                for trusted in TRUSTED_DOMAINS
            ) else "UNASSESSED",
            "published": item.get("published"),
        })

    count = len(matches)
    score = min(100, count * 10 + sum(
        10 for match in matches if match["source_quality"] == "ESTABLISHED"
    ))
    score = min(100, score)
    status = (
        "CORROBORATED" if sum(1 for m in matches if m["source_quality"] == "ESTABLISHED") >= 2
        else "PARTIALLY_CORROBORATED" if count == 1
        else "UNVERIFIED"
    )
    notes = [
        "Search-result matches indicate corroboration, not proof that claims are true.",
        "Publisher independence and factual accuracy require human review.",
    ]
    if result.get("status") != "SUCCESS":
        notes.append("Corroboration search failed or returned no usable results.")

    return {
        "verification_status": status,
        "verification_score": score,
        "independent_sources": count,
        "source_domains": sorted(domains),
        "matching_evidence": matches,
        "verification_notes": notes,
        "verification_query_provider": result.get("provider"),
        "verification_search_status": result.get("status"),
    }
