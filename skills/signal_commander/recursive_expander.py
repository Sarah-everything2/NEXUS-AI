"""NEXUS controlled recursive niche expansion with persistent memory."""

from skills.signal_commander.subniche_expander import expand_subniches
from skills.signal_commander.discovery_memory import remember_niche

MAX_DEPTH = 3
MAX_BRANCHES = 4


async def expand_tree(niche, depth=0, max_depth=MAX_DEPTH, seen=None, parent=None, evidence=None, source=None):
    if seen is None:
        seen = set()

    niche = niche.strip() if isinstance(niche, str) else ""
    key = niche.lower()

    if not niche or key in seen:
        return {"niche": niche, "depth": depth, "children": [], "status": "STOPPED"}

    seen.add(key)

    remember_niche(niche, parent=parent, evidence=evidence, source=source)

    if depth >= max_depth:
        return {"niche": niche, "depth": depth, "children": [], "status": "DEPTH_LIMIT"}

    result = await expand_subniches(niche, MAX_BRANCHES)

    node = {
        "niche": niche,
        "depth": depth,
        "status": result.get("status", "UNKNOWN"),
        "children": [],
    }

    if result.get("status") != "SUCCESS":
        node["error"] = result.get("error")
        return node

    for child in result.get("subniches", [])[:MAX_BRANCHES]:
        child_name = child.get("subniche_candidate", "").strip()

        if not child_name or child_name.lower() in seen:
            continue

        child_node = await expand_tree(
            child_name,
            depth=depth + 1,
            max_depth=max_depth,
            seen=seen,
            parent=niche,
            evidence=child.get("evidence"),
            source=child.get("url"),
        )

        child_node["evidence"] = child.get("evidence", "")
        child_node["source"] = child.get("url", "")
        node["children"].append(child_node)

    return node


async def discover_niche_tree(niche, max_depth=MAX_DEPTH):
    max_depth = max(1, min(int(max_depth), MAX_DEPTH))

    tree = await expand_tree(niche, max_depth=max_depth)

    return {
        "status": "SUCCESS" if tree.get("status") == "SUCCESS" else "ERROR",
        "root": niche,
        "max_depth": max_depth,
        "tree": tree,
        "error": tree.get("error"),
    }
