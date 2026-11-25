import asyncio
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from skills.signal_commander.niche_catalog import NICHES
from skills.signal_commander.opportunity_ranker import rank_opportunities
from tools.trend_discovery import discover_trends


RESEARCH_DIR = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "x_growth"
    / "research"
)


async def research_query(category, query, limit=5):
    try:
        result = await discover_trends(
            query=query,
            max_results=limit,
            timelimit="w",
        )

        if result.get("status") != "SUCCESS":
            return {
                "category": category,
                "query": query,
                "status": "ERROR",
                "stories": [],
                "error": result.get("error", "Search failed"),
            }

        stories = []

        for item in result.get("results", []):
            story = dict(item)
            story["category"] = category
            story["research_query"] = query
            published = story.get("published")
            try:
                published_dt = datetime.fromisoformat(str(published).replace("Z", "+00:00"))
                if published_dt.tzinfo is None:
                    published_dt = published_dt.replace(tzinfo=timezone.utc)
                age = datetime.now(timezone.utc) - published_dt.astimezone(timezone.utc)
                if age > timedelta(days=7) or age < -timedelta(days=1):
                    continue
                story["freshness_status"] = "VERIFIED_FRESH"
            except (ValueError, TypeError):
                story["freshness_status"] = "UNVERIFIED_DATE"
            stories.append(story)

        return {
            "category": category,
            "query": query,
            "status": "SUCCESS",
            "stories": stories,
        }

    except Exception as exc:
        return {
            "category": category,
            "query": query,
            "status": "ERROR",
            "stories": [],
            "error": str(exc)[:200],
        }


async def discover_x_opportunities(
    queries_per_category=2,
    stories_per_query=5,
):
    if not isinstance(queries_per_category, int) or not 1 <= queries_per_category <= 7:
        raise ValueError("queries_per_category must be between 1 and 7.")

    if not isinstance(stories_per_query, int) or not 1 <= stories_per_query <= 10:
        raise ValueError("stories_per_query must be between 1 and 10.")

    reports = []
    grouped = {}

    for category, queries in NICHES.items():
        for query in queries[:queries_per_category]:
            result = await research_query(
                category,
                query,
                stories_per_query,
            )
            reports.append(result)

            for story in result["stories"]:
                identity = (
                    story.get("href")
                    or story.get("url")
                    or story.get("title")
                    or ""
                ).strip().lower()

                if not identity:
                    continue

                if identity not in grouped:
                    grouped[identity] = dict(story)
                    grouped[identity]["matched_categories"] = []

                if category not in grouped[identity]["matched_categories"]:
                    grouped[identity]["matched_categories"].append(category)

    ranked = []

    for story in grouped.values():
        categories = story["matched_categories"]
        scored = rank_opportunities(
            [story],
            niche=categories[0] if categories else "",
            repeat_counts={
                (
                    story.get("href")
                    or story.get("url")
                    or story.get("title")
                    or ""
                ).strip().lower(): len(categories)
            },
        )

        if scored:
            scored[0]["description"] = (
                story.get("body") or story.get("description") or ""
            )
            scored[0]["url"] = (
                story.get("href") or story.get("url") or ""
            )
            scored[0]["matched_categories"] = categories
            scored[0]["research_query"] = story.get("research_query", "")
            scored[0]["published"] = story.get("published")
            scored[0]["freshness_status"] = story.get("freshness_status", "UNVERIFIED_DATE")
            ranked.extend(scored)

    ranked.sort(key=lambda item: item["score"], reverse=True)

    successful = sum(
        report["status"] == "SUCCESS" for report in reports
    )

    report = {
        "report_id": uuid.uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "research_engine": "NEXUS Signal Commander + web discovery",
        "research_type": "MULTI_NICHE_X_OPPORTUNITY_DISCOVERY",
        "categories_available": len(NICHES),
        "categories_searched": len({
            report["category"]
            for report in reports
        }),
        "queries_attempted": len(reports),
        "successful_queries": successful,
        "failed_queries": len(reports) - successful,
        "stories_found": len(ranked),
        "ranking_note": (
            "Estimated discovery opportunity, not verified X virality "
            "or audience demand."
        ),
        "reports": reports,
        "top_opportunities": ranked[:30],
    }

    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

    path = RESEARCH_DIR / f"{report['report_id']}.json"
    temporary_path = RESEARCH_DIR / f".{report['report_id']}.tmp"

    try:
        temporary_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    report["saved_to"] = str(path)
    report["status"] = (
        "SUCCESS" if successful == len(reports)
        else "PARTIAL" if successful
        else "ERROR"
    )

    return report
