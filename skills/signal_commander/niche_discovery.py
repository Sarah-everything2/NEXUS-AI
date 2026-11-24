"""NEXUS AI dynamic niche discovery engine."""

import asyncio
from ddgs import DDGS

MAX_QUERY_RESULTS = 8


SEED_DISCOVERY_QUERIES = [
    "emerging niches gaining popularity online",
    "fast growing communities and new internet trends",
    "new industries technologies and emerging markets",
    "viral topics and emerging content niches",
]


async def search_niche_candidates(query, max_results=8):
    max_results = max(1, min(int(max_results), MAX_QUERY_RESULTS))

    def search():
        return list(
            DDGS().text(
                query,
                safesearch="moderate",
                max_results=max_results,
            )
        )

    try:
        results = await asyncio.to_thread(search)
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("href", ""),
                "snippet": item.get("body", ""),
                "discovery_query": query,
                "source": "web_search",
            }
            for item in results
        ]
    except Exception as exc:
        return {
            "status": "ERROR",
            "query": query,
            "error": str(exc)[:200],
        }


async def discover_niche_candidates(max_results_per_query=5):
    discoveries = []

    for query in SEED_DISCOVERY_QUERIES:
        results = await search_niche_candidates(
            query,
            max_results=max_results_per_query,
        )

        if isinstance(results, list):
            discoveries.extend(results)

    unique = {}
    for item in discoveries:
        key = item["title"].strip().lower()
        if key and key not in unique:
            unique[key] = item

    return {
        "status": "SUCCESS",
        "queries_used": len(SEED_DISCOVERY_QUERIES),
        "candidates_found": len(unique),
        "candidates": list(unique.values()),
    }
