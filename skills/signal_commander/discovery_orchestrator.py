"""Unified recursive niche and trend discovery pipeline."""

import asyncio
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from skills.signal_commander.recursive_expander import discover_niche_tree
from skills.signal_commander.discovery_memory import remember_niche, remember_trend
from skills.signal_commander.opportunity_ranker import rank_opportunities
from skills.signal_commander.report_engine import save_report
from tools.trend_discovery import discover_trends
from skills.signal_commander.cross_category_intelligence import run_cross_category_discovery
from skills.signal_commander.story_verifier import verify_story

MAX_NICHES = 20
MAX_DEPTH = 2
MAX_STORIES_PER_NICHE = 8
MAX_CONCURRENT_SEARCHES = 3
MAX_VERIFICATIONS = 10


def _identity(item):
    url = (item.get("url") or item.get("href") or "").strip()
    if url:
        try:
            parts = urlsplit(url)
            host = (parts.hostname or "").lower().removeprefix("www.")
            path = parts.path.rstrip("/")
            query = urlencode(sorted(
                (k, v) for k, v in parse_qsl(parts.query)
                if not k.lower().startswith("utm_")
                and k.lower() not in {"fbclid", "gclid", "ref"}
            ))
            if host:
                return urlunsplit((parts.scheme.lower() or "https", host, path, query, ""))
        except (TypeError, ValueError):
            pass
    return " ".join((item.get("title") or "").lower().split())


def flatten_tree(node, output=None):
    if output is None:
        output = []
    if not isinstance(node, dict) or len(output) >= MAX_NICHES:
        return output

    niche = node.get("niche", "")
    niche = niche.strip() if isinstance(niche, str) else ""

    if niche and niche.casefold() not in {x.casefold() for x in output}:
        output.append(niche)

    for child in node.get("children", []):
        if len(output) >= MAX_NICHES:
            break
        flatten_tree(child, output)
    return output


async def discover_for_niche(niche, semaphore):
    async with semaphore:
        try:
            result = await discover_trends(
                query=f"latest developments trending news {niche}",
                max_results=MAX_STORIES_PER_NICHE,
                timelimit="w",
            )
            if result.get("status") != "SUCCESS":
                return {
                    "niche": niche, "status": "ERROR", "stories": [],
                    "error": result.get("error", "Trend search failed"),
                }

            stories = result.get("results", [])
            ranked = rank_opportunities(stories, niche=niche)

            for story in ranked:
                remember_trend(
                    story.get("title", ""),
                    niche=niche,
                    evidence=story.get("body") or story.get("description") or story.get("title", ""),
                    source=story.get("href") or story.get("url", ""),
                )

            return {
                "niche": niche, "status": "SUCCESS",
                "stories_found": len(stories), "stories": ranked,
            }
        except Exception as exc:
            return {
                "niche": niche, "status": "ERROR", "stories": [],
                "error": str(exc)[:200],
            }


async def run_discovery(root_niche="Artificial Intelligence", prepare_agent_handoff=True):
    if not isinstance(root_niche, str) or not root_niche.strip():
        raise ValueError("A root niche is required.")

    root_niche = root_niche.strip()
    remember_niche(root_niche)

    expansion = await discover_niche_tree(root_niche, max_depth=MAX_DEPTH)
    tree = expansion.get("tree", {})
    niches = flatten_tree(tree) or [root_niche]
    niches = niches[:MAX_NICHES]

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SEARCHES)
    results = await asyncio.gather(
        *(discover_for_niche(niche, semaphore) for niche in niches),
        return_exceptions=True,
    )

    reports = []
    grouped = {}

    for result in results:
        if isinstance(result, Exception):
            reports.append({"status": "ERROR", "error": str(result)[:200]})
            continue

        reports.append(result)
        for story in result.get("stories", []):
            key = _identity(story)
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
        story["url"] = story.get("url") or story.get("href") or ""
        story["href"] = story["url"]

        scored = rank_opportunities(
            [story],
            niche=found[0] if found else root_niche,
            repeat_counts={_identity(story): len(found)},
        )
        if scored:
            scored[0]["discovered_niches"] = found
            ranked.append(scored[0])

    cross_category = {}
    try:
        cross_category = await run_cross_category_discovery(
            max_pairs=8, results_per_pair=3
        )
    except Exception as exc:
        cross_category = {"status": "ERROR", "error": str(exc)[:200]}

    cross_ranked = []
    for discovery in cross_category.get("discoveries", []):
        categories = discovery.get("categories", [])
        topic = (discovery.get("topic") or "").strip()
        source = (discovery.get("source") or "").strip()
        evidence = discovery.get("evidence", "")

        if not topic:
            continue

        item = {
            "title": topic, "description": evidence,
            "body": evidence, "url": source, "href": source,
        }
        identity = _identity(item)

        existing = next(
            (s for s in ranked if _identity(s) == identity),
            None,
        )
        if existing:
            connections = existing.setdefault("cross_category_connections", [])
            if categories and categories not in connections:
                connections.append(categories)
            continue

        scored = rank_opportunities(
            [item], niche=" + ".join(categories) or root_niche
        )
        if not scored:
            continue

        opportunity = scored[0]
        opportunity.update({
            "opportunity_type": "CROSS_CATEGORY",
            "categories": categories,
            "evidence": evidence,
            "cross_category_bonus": 5,
            "base_score": opportunity["score"],
            "score": min(100, round(opportunity["score"] + 5, 2)),
        })
        cross_ranked.append(opportunity)

    ranked.extend(cross_ranked)

    verify_candidates = ranked[:MAX_VERIFICATIONS]
    verification_semaphore = asyncio.Semaphore(2)

    async def _verify_opportunity(item):
        async with verification_semaphore:
            try:
                result = await verify_story(item)
            except Exception as exc:
                result = {
                    "verification_status": "UNVERIFIED",
                    "verification_score": 0,
                    "independent_sources": 0,
                    "source_domains": [],
                    "matching_evidence": [],
                    "verification_notes": [str(exc)[:160]],
                }

        item.update(result)
        bonus = (
            5 if result.get("verification_status") == "CORROBORATED"
            else 2 if result.get("verification_status") == "PARTIALLY_CORROBORATED"
            else 0
        )
        item["pre_verification_score"] = item.get("score", 0)
        item["verification_bonus"] = bonus
        item["score"] = min(100, round(item.get("score", 0) + bonus, 2))

    await asyncio.gather(
        *(_verify_opportunity(item) for item in verify_candidates)
    )
    ranked.sort(key=lambda item: item.get("score", 0), reverse=True)

    successful = sum(
        1 for report in reports if report.get("status") == "SUCCESS"
    )

    output = {
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
        "verified_opportunities": sum(
            1 for item in verify_candidates
            if item.get("verification_status") == "CORROBORATED"
        ),
        "reports": reports,
        "top_opportunities": ranked[:20],
        "cross_category_intelligence": cross_category,
        "discovery_tree": tree,
        "publishing_enabled": False,
        "agent_handoff": {
            "status": "PENDING",
            "tasks_created": 0,
            "tasks": [],
            "execution_started": False,
        },
    }

    if prepare_agent_handoff:
        try:
            from agents.dispatcher import dispatch_opportunities
            output["agent_handoff"] = dispatch_opportunities(
                output["top_opportunities"][:10],
                max_tasks=10,
            )
        except Exception as exc:
            output["agent_handoff"] = {
                "status": "ERROR",
                "tasks_created": 0,
                "tasks": [],
                "error": str(exc)[:200],
                "execution_started": False,
            }
    try:
        output["report_file"] = save_report(output)
        output["report_status"] = "SAVED"
    except Exception as exc:
        output["report_status"] = "ERROR"
        output["report_error"] = str(exc)[:200]

    return output


if __name__ == "__main__":
    result = asyncio.run(run_discovery())
    print("STATUS:", result["status"])
    print("NICHES SCANNED:", result["niches_scanned"])
    print("SUCCESSFUL SCANS:", result["successful_scans"])
    print("FAILED SCANS:", result["failed_scans"])
    print("STORIES FOUND:", result["total_stories"])
    print("CROSS-CATEGORY:", result["cross_category_opportunities"])
    print("VERIFIED:", result["verified_opportunities"])
    print("REPORT:", result.get("report_file", result.get("report_error", "Not saved")))

    print("\nTOP OPPORTUNITIES:")
    for story in result["top_opportunities"][:10]:
        print(f'{story["score"]:>6} | {story["title"]}')
        print(story.get("url", ""))
