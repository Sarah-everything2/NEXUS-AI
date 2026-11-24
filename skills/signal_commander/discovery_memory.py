"""Persistent memory for NEXUS niche and trend discoveries."""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

MEMORY_FILE = Path("data/signal_commander/discovery_memory.json")


def _load():
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not MEMORY_FILE.exists():
        data = {}
    else:
        try:
            data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except (json.JSONDecodeError, OSError):
            data = {}

    for key in ("niches", "trends", "relationships"):
        if not isinstance(data.get(key), dict):
            data[key] = {}

    return data


def _save(data):
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = MEMORY_FILE.with_suffix(".tmp")
    temp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temp.replace(MEMORY_FILE)


def _key(value):
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()[:20]


def remember_niche(niche, parent=None, evidence=None, source=None):
    if not niche or not niche.strip():
        return {"status": "ERROR", "error": "Niche is required"}

    data = _load()
    key = _key(niche)

    existing = data["niches"].get(key)
    now = datetime.now(timezone.utc).isoformat()

    if existing:
        existing["last_seen"] = now
        existing["discovery_count"] = existing.get("discovery_count", 1) + 1

        if evidence:
            existing["evidence"] = evidence[:1000]
        if source:
            existing["source"] = source

        _save(data)
        return {"status": "EXISTS", "niche": niche, "record": existing}

    record = {
        "name": niche.strip(),
        "parent": parent,
        "first_seen": now,
        "last_seen": now,
        "discovery_count": 1,
        "evidence": (evidence or "")[:1000],
        "source": source or "",
    }

    data["niches"][key] = record
    _save(data)

    return {"status": "SAVED", "niche": niche, "record": record}


def remember_trend(trend, niche=None, evidence=None, source=None):
    if not trend or not trend.strip():
        return {"status": "ERROR", "error": "Trend is required"}

    data = _load()
    key = _key(trend)
    now = datetime.now(timezone.utc).isoformat()

    existing = data["trends"].get(key)

    if existing:
        existing["last_seen"] = now
        existing["discovery_count"] = existing.get("discovery_count", 1) + 1

        if niche:
            niches = existing.setdefault("discovered_niches", [])
            if niche not in niches:
                niches.append(niche)

        if evidence:
            existing["evidence"] = evidence[:1000]

        if source:
            existing["source"] = source

        _save(data)
        return {"status": "EXISTS", "trend": trend, "record": existing}

    record = {
        "name": trend.strip(),
        "niche": niche,
        "discovered_niches": [niche] if niche else [],
        "first_seen": now,
        "last_seen": now,
        "discovery_count": 1,
        "evidence": (evidence or "")[:1000],
        "source": source or "",
    }

    data["trends"][key] = record
    _save(data)

    return {"status": "SAVED", "trend": trend, "record": record}



def remember_relationship(category_a, category_b, topic, evidence=None, source=None):
    if not all(isinstance(v, str) and v.strip() for v in (category_a, category_b, topic)):
        return {"status": "ERROR", "error": "Two categories and a topic are required"}

    categories = sorted([category_a.strip(), category_b.strip()], key=str.lower)
    data = _load()
    key = _key("::".join(categories) + "::" + topic)
    now = datetime.now(timezone.utc).isoformat()
    existing = data["relationships"].get(key)

    if existing:
        existing["last_seen"] = now
        existing["discovery_count"] = existing.get("discovery_count", 1) + 1
        if evidence:
            existing["evidence"] = evidence[:1000]
        if source:
            existing["source"] = source
        _save(data)
        return {"status": "EXISTS", "record": existing}

    record = {
        "categories": categories,
        "topic": topic.strip(),
        "first_seen": now,
        "last_seen": now,
        "discovery_count": 1,
        "evidence": (evidence or "")[:1000],
        "source": source or "",
    }
    data["relationships"][key] = record
    _save(data)
    return {"status": "SAVED", "record": record}

def get_discovery_memory():
    data = _load()
    return {
        "status": "SUCCESS",
        "niche_count": len(data["niches"]),
        "trend_count": len(data["trends"]),
        "relationship_count": len(data["relationships"]),
        "niches": list(data["niches"].values()),
        "trends": list(data["trends"].values()),
        "relationships": list(data["relationships"].values()),
    }
