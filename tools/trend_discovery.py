import asyncio
import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
from xml.etree import ElementTree

import httpx
from ddgs import DDGS


ALLOWED_TIME_FILTERS = {"d", "w", "m", "y"}

TIME_FILTERS = {
    "d": "1d",
    "w": "7d",
    "m": "30d",
    "y": "365d",
}


def clean_text(value):
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_date(value):
    if not value:
        return None

    try:
        value = str(value).strip()

        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            dt = parsedate_to_datetime(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc).isoformat()

    except (ValueError, TypeError, OverflowError):
        return None


def normalize_result(item, provider):
    item = dict(item)

    published = (
        item.get("published")
        or item.get("published_at")
        or item.get("date")
        or item.get("datetime")
    )

    return {
        **item,
        "title": clean_text(item.get("title")),
        "href": (
            item.get("href")
            or item.get("url")
            or ""
        ).strip(),
        "body": clean_text(
            item.get("body")
            or item.get("description")
            or ""
        ),
        "published": normalize_date(published),
        "source": item.get("source") or provider,
    }


async def google_news_search(query, max_results, timelimit):
    search_query = f"{query} when:{TIME_FILTERS[timelimit]}"

    params = {
        "q": search_query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }

    url = (
        "https://news.google.com/rss/search?"
        + urlencode(params)
    )

    headers = {
        "User-Agent": "NEXUS-AI/1.0 research discovery"
    }

    async with httpx.AsyncClient(
        timeout=20,
        follow_redirects=True,
        headers=headers,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

    root = ElementTree.fromstring(response.content)
    results = []

    for item in root.findall(".//item")[:max_results]:
        results.append(normalize_result({
            "title": item.findtext("title"),
            "href": item.findtext("link", ""),
            "body": item.findtext("description", ""),
            "published": item.findtext("pubDate", ""),
        }, "Google News RSS"))

    return results


async def discover_trends(
    query,
    max_results=10,
    region="wt-wt",
    timelimit="w",
):
    """Discover recent stories using DDGS with Google News fallback."""

    if not isinstance(query, str) or not query.strip():
        raise ValueError("A search query is required.")

    if len(query) > 300:
        raise ValueError("Search query is too long.")

    if not isinstance(max_results, int) or not 1 <= max_results <= 20:
        raise ValueError("max_results must be between 1 and 20.")

    if timelimit not in ALLOWED_TIME_FILTERS:
        raise ValueError("Time filter must be d, w, m or y.")

    if not isinstance(region, str) or len(region) > 20:
        raise ValueError("Invalid search region.")

    query = query.strip()
    ddgs_error = None

    try:
        def search():
            return list(
                DDGS(timeout=10).text(
                    query,
                    region=region,
                    safesearch="moderate",
                    timelimit=timelimit,
                    max_results=max_results,
                    backend="auto",
                )
            )

        results = await asyncio.to_thread(search)

        if results:
            normalized = [
                normalize_result(item, "DDGS")
                for item in results[:max_results]
            ]

            return {
                "status": "SUCCESS",
                "query": query,
                "provider": "DDGS",
                "time_filter": timelimit,
                "result_count": len(normalized),
                "results": normalized,
                "fallback_used": False,
            }

    except Exception as exc:
        ddgs_error = f"{type(exc).__name__}: {str(exc)[:200]}"

    try:
        results = await google_news_search(
            query,
            max_results,
            timelimit,
        )

        return {
            "status": "SUCCESS" if results else "ERROR",
            "query": query,
            "provider": "Google News RSS",
            "time_filter": timelimit,
            "result_count": len(results),
            "results": results,
            "fallback_used": True,
            "primary_error": ddgs_error,
            "error": None if results else "Google News returned no results.",
        }

    except Exception as exc:
        return {
            "status": "ERROR",
            "query": query,
            "provider": None,
            "time_filter": timelimit,
            "result_count": 0,
            "results": [],
            "fallback_used": True,
            "primary_error": ddgs_error,
            "error": f"{type(exc).__name__}: {str(exc)[:200]}",
        }
