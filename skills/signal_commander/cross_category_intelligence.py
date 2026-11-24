"""Evidence-backed cross-category intelligence for NEXUS Signal Commander."""

import asyncio
import re
import time
from ddgs import DDGS

from skills.signal_commander.niche_catalog import NICHES
from skills.signal_commander.discovery_memory import remember_relationship


PAIR_CANDIDATES = [
    ("Artificial Intelligence", "Mining"),
    ("Artificial Intelligence", "Finance & Stocks"),
    ("Artificial Intelligence", "Politics"),
    ("Artificial Intelligence", "Football"),
    ("Artificial Intelligence", "Basketball"),
    ("Artificial Intelligence", "Engineering"),
    ("Artificial Intelligence", "Technology"),
    ("Mining", "Finance & Stocks"),
    ("Mining", "Engineering"),
    ("Mining", "Politics"),
    ("Mining", "Technology"),
    ("Cryptocurrency", "Finance & Stocks"),
    ("Cryptocurrency", "Technology"),
    ("Cryptocurrency", "Politics"),
    ("Business & Startups", "Artificial Intelligence"),
    ("Business & Startups", "Finance & Stocks"),
    ("Engineering", "Technology"),
    ("Politics", "Technology"),
    ("Science & Discovery", "Health & Wellness"),
]

ALIASES = {
    "Artificial Intelligence": ["artificial intelligence", "ai", "machine learning"],
    "Mining": ["mining", "minerals", "mineral exploration", "gold mining"],
    "Finance & Stocks": ["finance", "financial", "stocks", "investment", "markets"],
    "Politics": ["politics", "political", "government", "policy", "elections"],
    "Football": ["football", "soccer", "premier league"],
    "Basketball": ["basketball", "nba", "wnba"],
    "Engineering": ["engineering", "engineers", "manufacturing"],
    "Technology": ["technology", "tech", "software", "cybersecurity"],
    "Cryptocurrency": ["cryptocurrency", "crypto", "bitcoin", "blockchain"],
    "Business & Startups": ["business", "startups", "entrepreneurship", "companies"],
    "Science & Discovery": ["science", "scientific", "research", "discovery"],
    "Health & Wellness": ["health", "healthcare", "medical", "wellness"],
    "Healthcare": ["healthcare", "medical", "health"],
}


def _valid_pairs():
    available = {name.lower(): name for name in NICHES}
    return [
        (available[a.lower()], available[b.lower()])
        for a, b in PAIR_CANDIDATES
        if a.lower() in available and b.lower() in available
    ]


def _matches_category(text, category):
    aliases = ALIASES.get(category, [category])
    return any(
        re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text, re.I)
        for alias in aliases
    )


def _relevant(text, pair):
    return all(_matches_category(text, category) for category in pair)


def _search_pair(pair, results_per_pair):
    a, b = pair

    queries = [
        f"{a} {b} real world applications developments",
        f"how {a} is transforming {b} industry",
    ]

    collected = {}
    errors = []

    for query in queries:
        for attempt in range(2):
            try:
                results = list(DDGS().text(
                    query,
                    safesearch="moderate",
                    max_results=results_per_pair,
                ))

                for item in results:
                    title = (item.get("title") or "").strip()
                    snippet = (item.get("body") or "").strip()
                    source = (item.get("href") or "").strip()

                    if (
                        not title
                        or len(title) > 180
                        or len(title.split()) > 24
                        or not source.startswith(("http://", "https://"))
                    ):
                        continue

                    evidence = f"{title}. {snippet}"[:1000]

                    if not _relevant(evidence, pair):
                        continue

                    collected.setdefault(title.casefold(), {
                        "title": title,
                        "evidence": evidence,
                        "source": source,
                    })

                break

            except Exception as exc:
                message = str(exc)[:200]

                if "No results found" in message:
                    break

                if attempt == 0:
                    time.sleep(1)
                else:
                    errors.append(message)

        if len(collected) >= results_per_pair:
            break

    return pair, list(collected.values())[:results_per_pair], errors


async def run_cross_category_discovery(max_pairs=8, results_per_pair=5):
    max_pairs = max(1, min(int(max_pairs), 20))
    results_per_pair = max(1, min(int(results_per_pair), 8))

    pairs = _valid_pairs()[:max_pairs]

    if not pairs:
        return {"status": "ERROR", "error": "No valid category pairings"}

    semaphore = asyncio.Semaphore(2)

    async def limited_search(pair):
        async with semaphore:
            return await asyncio.to_thread(
                _search_pair, pair, results_per_pair
            )

    outcomes = await asyncio.gather(*[
        limited_search(pair) for pair in pairs
    ])

    discoveries = []
    errors = []
    empty_pairs = []
    successful_pairs = 0

    for pair, results, pair_errors in outcomes:
        if pair_errors:
            errors.append({
                "categories": list(pair),
                "errors": pair_errors,
            })

        if not results:
            if pair_errors:
                continue
            empty_pairs.append(list(pair))
            continue

        successful_pairs += 1

        for item in results:
            saved = remember_relationship(
                pair[0],
                pair[1],
                item["title"],
                evidence=item["evidence"],
                source=item["source"],
            )

            if saved.get("status") in ("SAVED", "EXISTS"):
                discoveries.append({
                    "categories": list(pair),
                    "topic": item["title"],
                    "evidence": item["evidence"],
                    "source": item["source"],
                    "memory_status": saved["status"],
                })


    return {
        "status": (
            "SUCCESS" if not errors and not empty_pairs
            else "PARTIAL" if discoveries
            else "ERROR" if errors
            else "NO_RELEVANT_RESULTS"
        ),
        "pairs_checked": len(pairs),
        "successful_pairs": successful_pairs,
        "discoveries_found": len(discoveries),
        "empty_pairs": empty_pairs,
        "errors": errors,
        "discoveries": discoveries,
    }
