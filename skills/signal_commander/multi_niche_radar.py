"""NEXUS Signal Commander - Expanded multi-niche YouTube discovery."""

from datetime import datetime, timezone

from skills.ai_to_earn.trend_engine.youtube import search_youtube
from skills.signal_commander.niche_catalog import NICHES
from skills.signal_commander.trend_radar import rank_signals
from skills.signal_commander.report_engine import save_report
from skills.signal_commander.metadata_enricher import enrich_top_metadata


def discover_all_niches(queries_per_category=2, limit_per_query=2):
    discovered = []
    seen = {}
    category_status = {}

    for category, queries in NICHES.items():
        print(f"\n[RADAR] Searching: {category}")

        category_count = 0
        query_results = []
        errors = []

        for query in queries[:max(1, int(queries_per_category))]:
            print(f"  [QUERY] {query}")

            try:
                videos = search_youtube(
                    query,
                    limit=max(1, min(int(limit_per_query), 5))
                )

                query_results.append({
                    "query": query,
                    "videos_found": len(videos),
                    "status": "SUCCESS"
                })

                for video in videos:
                    item = dict(video)
                    video_id = item.get("video_id") or item.get("url")

                    if not video_id:
                        video_id = item.get("title", "").strip().lower()

                    if video_id in seen:
                        existing = seen[video_id]

                        if category not in existing["matched_niches"]:
                            existing["matched_niches"].append(category)

                        if query not in existing["research_queries"]:
                            existing["research_queries"].append(query)

                        continue

                    item["niche"] = category
                    item["matched_niches"] = [category]
                    item["research_query"] = query
                    item["research_queries"] = [query]

                    upload_date = item.get("upload_date")
                    age_hours = None

                    if upload_date:
                        try:
                            published = datetime.strptime(
                                upload_date, "%Y%m%d"
                            ).replace(tzinfo=timezone.utc)

                            age_hours = max(
                                0,
                                (datetime.now(timezone.utc) - published)
                                .total_seconds() / 3600
                            )
                        except (ValueError, TypeError):
                            pass

                    item["age_hours"] = age_hours
                    item["age_data_status"] = (
                        "MEASURED" if age_hours is not None else "UNKNOWN"
                    )

                    item["competition_status"] = "UNMEASURED"
                    item["data_quality"] = {
                        "views": "AVAILABLE" if item.get("views") else "MISSING",
                        "upload_date": "AVAILABLE" if upload_date else "MISSING",
                        "competition": "NOT_MEASURED"
                    }

                    seen[video_id] = item
                    discovered.append(item)
                    category_count += 1

            except Exception as exc:
                errors.append({
                    "query": query,
                    "error": str(exc)[:200]
                })
                print(f"  [QUERY ERROR] {str(exc)[:150]}")

        category_status[category] = {
            "status": (
                "ERROR" if errors and not query_results
                else "PARTIAL" if errors
                else "SUCCESS"
            ),
            "queries_attempted": len(query_results) + len(errors),
            "queries_succeeded": len(query_results),
            "unique_videos_found": category_count,
            "query_results": query_results,
            "errors": errors
        }

    baseline_ranked = rank_signals(discovered)
    enrich_top_metadata(baseline_ranked, limit=3)
    ranked = rank_signals(baseline_ranked)

    report = {
        "project": "NEXUS SIGNAL COMMANDER",
        "research_type": "EXPANDED_MULTI_NICHE_YOUTUBE",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "categories_searched": len(NICHES),
        "queries_per_category": queries_per_category,
        "videos_per_query": limit_per_query,
        "total_queries_attempted": sum(
            value["queries_attempted"]
            for value in category_status.values()
        ),
        "videos_discovered": len(discovered),
        "category_status": category_status,
        "ranking": "NEXUS SIGNAL RADAR - BASELINE",
        "competition_data": "NOT MEASURED",
        "health_content_notice": (
            "Health content requires credible source verification "
            "and human review before publication."
        ),
        "publishing_enabled": False,
        "stories": ranked
    }

    report_path = save_report(report)

    print("\n========== EXPANDED MULTI-NICHE RADAR ==========")

    for index, item in enumerate(ranked, 1):
        print(
            f"{index}. [{item['niche']}] "
            f"{item.get('title', 'Untitled')} "
            f"| Score: {item['radar']['score']} "
            f"| Views: {item.get('views', 0)}"
        )

    print("\nCATEGORIES:", len(NICHES))
    print("QUERIES:", report["total_queries_attempted"])
    print("UNIQUE VIDEOS:", len(discovered))
    print("REPORT:", report_path)

    return report


if __name__ == "__main__":
    discover_all_niches()
