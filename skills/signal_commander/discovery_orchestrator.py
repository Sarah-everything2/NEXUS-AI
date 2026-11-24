"""NEXUS unified recursive niche and trend discovery orchestrator."""

import asyncio

from skills.signal_commander.recursive_expander import discover_niche_tree
from skills.signal_commander.discovery_memory import remember_niche, remember_trend
from skills.signal_commander.opportunity_ranker import rank_opportunities
from tools.trend_discovery import discover_trends
from skills.signal_commander.cross_category_intelligence import run_cross_category_discovery

MAX_NICHES = 20
MAX_DEPTH = 2
MAX_STORIES_PER_NICHE = 8


def flatten_tree(node, output=None):
    if output is None:
        output = []

    if not isinstance(node, dict) or len(output) >= MAX_NICHES:
        return output

    niche = node.get("niche", "").strip()

    if niche and niche.lower() not in {x.lower() for x in output}:
        output.append(niche)

    for child in node.get("children", []):
        if len(output) >= MAX_NICHES:
            break
        flatten_tree(child, output)

    return output


async def discover_for_niche(niche):
    try:
        result = await discover_trends(
            query=f"latest developments trending news {niche}",
            max_results=MAX_STORIES_PER_NICHE,
            timelimit="w",
        )

        if result.get("status") != "SUCCESS":
            return {
                "niche": niche,
                "status": "ERROR",
                "stories": [],
                "error": result.get("error", "Trend search failed"),
            }

        stories = result.get("results", [])
        ranked = rank_opportunities(stories, niche=niche)

        for story in ranked:
            remember_trend(
                story.get("title", ""),
                niche=niche,
                evidence=story.get("title", ""),
                source=story.get("href") or story.get("url", ""),
            )

        return {
            "niche": niche,
            "status": "SUCCESS",
            "stories_found": len(stories),
            "stories": ranked,
        }

    except Exception as exc:
        return {
            "niche": niche,
            "status": "ERROR",
            "stories": [],
            "error": str(exc)[:200],
        }


async def run_discovery(root_niche="Artificial Intelligence"):
    if not isinstance(root_niche, str) or not root_niche.strip():
        raise ValueError("A root niche is required.")

    root_niche = root_niche.strip()
    remember_niche(root_niche)

    expansion = await discover_niche_tree(
        root_niche,
        max_depth=MAX_DEPTH,
    )

    tree = expansion.get("tree", {})
    niches = flatten_tree(tree)

    if not niches:
        niches = [root_niche]

    niches = niches[:MAX_NICHES]

    results = await asyncio.gather(
        *(discover_for_niche(niche) for niche in niches),
        return_exceptions=True,
    )

    reports = []
    grouped = {}

    for result in results:
        if isinstance(result, Exception):
            reports.append({
                "status": "ERROR",
                "error": str(result)[:200],
            })
            continue

        reports.append(result)

        for story in result.get("stories", []):
            url = (
                story.get("href") or story.get("url") or ""
            ).strip().lower()
            title = (story.get("title") or "").strip().lower()
            key = url or title

            if not key:
                continue

            if key not in grouped:
                grouped[key] = dict(story)
                grouped[key]["discovered_niches"] = []

            niche = result.get("niche", "")

            if niche and niche not in grouped[key]["discovered_niches"]:
                grouped[key]["discovered_niches"].append(niche)

    ranked = []

    for story in grouped.values():
        found = story.get("discovered_niches", [])
        identity = (
            story.get("href")
            or story.get("url")
            or story.get("title")
            or ""
        ).strip().lower()

        counts = {identity: len(found)}

        ranked.extend(rank_opportunities(
            [story],
            niche=found[0] if found else root_niche,
            repeat_counts=counts,
        ))

        ranked[-1]["discovered_niches"] = found

    ranked.sort(key=lambda item: item.get("score", 0), reverse=True)

    successful = sum(
        1 for report in reports
        if report.get("status") == "SUCCESS"
    )

    for story in ranked:
        remember_trend(
            story.get("title", ""),
            niche=story.get("niche"),
            evidence=story.get("title", ""),
            source=story.get("url", ""),
        )

    try:
        cross_category = await run_cross_category_discovery(
            max_pairs=8,
            results_per_pair=3,
        )
    except Exception as exc:
        cross_category = {
            "status": "ERROR",
            "error": str(exc)[:200],
        }

    cross_ranked = []

    if cross_category.get("discoveries"):
        for discovery in cross_category["discoveries"]:
            categories = discovery.get("categories", [])
            topic = discovery.get("topic", "")
            source = discovery.get("source", "")
            evidence = discovery.get("evidence", "")

            if not topic:
                continue

            niche_label = " + ".join(categories) or root_niche

            item = {
                "title": topic,
                "description": evidence,
                "url": source,
            }

            scored = rank_opportunities(
                [item],
                niche=niche_label,
            )[0]

            identity = (source or topic).strip().lower()
            existing = next(
                (
                    story for story in ranked
                    if (
                        story.get("url") or story.get("title") or ""
                    ).strip().lower() == identity
                ),
                None,
            )

            if existing:
                connections = existing.setdefault(
                    "cross_category_connections", []
                )
                if categories not in connections:
                    connections.append(categories)

                if not existing.get("cross_category_bonus"):
                    existing["base_score"] = existing["score"]
                    existing["cross_category_bonus"] = 5
                    existing["score"] = min(
                        100, round(existing["score"] + 5, 2)
                    )
                continue

            scored["opportunity_type"] = "CROSS_CATEGORY"
            scored["categories"] = categories
            scored["evidence"] = evidence
            scored["cross_category_bonus"] = 5
            scored["base_score"] = scored["score"]
            scored["score"] = min(
                100, round(scored["score"] + 5, 2)
            )
            cross_ranked.append(scored)

    ranked.extend(cross_ranked)
    ranked.sort(key=lambda item: item.get("score", 0), reverse=True)

    return {
        "status": (
            "SUCCESS" if successful == len(niches)
            else "PARTIAL" if successful
            else "ERROR"
        ),
        "root_niche": root_niche,
        "niches_scanned": len(niches),
        "successful_scans": successful,
        "failed_scans": len(niches) - successful,
        "total_stories": len(ranked),
        "cross_category_opportunities": len(cross_ranked),
        "reports": reports,
        "top_opportunities": ranked[:20],
        "cross_category_intelligence": cross_category,
        "discovery_tree": tree,
    }


if __name__ == "__main__":
    result = asyncio.run(run_discovery())

    print("STATUS:", result["status"])
    print("NICHES SCANNED:", result["niches_scanned"])
    print("SUCCESSFUL SCANS:", result["successful_scans"])
    print("FAILED SCANS:", result["failed_scans"])
    print("STORIES FOUND:", result["total_stories"])

    print("\nTOP OPPORTUNITIES:")

    for story in result["top_opportunities"][:10]:
        print(f'{story["score"]:>6} | {story["title"]}')
        print(story.get("url", ""))
