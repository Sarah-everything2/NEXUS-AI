import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
SC_DIR = ROOT / "skills" / "signal_commander"
REPORT_DIR = SC_DIR / "reports"
MEMORY_FILE = ROOT / "data" / "signal_commander" / "discovery_memory.json"
TASK_FILE = ROOT / "data" / "signal_commander" / "agent_tasks.json"

def _read_json(path, default):
    try:
        if path.exists() and path.stat().st_size <= 5_000_000:
            with path.open("r", encoding="utf-8-sig") as f:
                return json.load(f)
    except Exception:
        pass
    return default

def _memory():
    data = _read_json(MEMORY_FILE, {})
    return data if isinstance(data, dict) else {}

def _tasks():
    data = _read_json(TASK_FILE, {"tasks": {}})
    records = data.get("tasks", {}) if isinstance(data, dict) else {}
    if isinstance(records, dict):
        return list(records.values())
    if isinstance(records, list):
        return records
    return []

def _reports():
    if not REPORT_DIR.exists():
        return []
    files = sorted(
        REPORT_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    result = []
    for path in files[:100]:
        data = _read_json(path, None)
        if isinstance(data, dict):
            result.append({
                "filename": path.name,
                "modified": datetime.fromtimestamp(
                    path.stat().st_mtime, timezone.utc
                ).isoformat(),
                "data": data
            })
    return result

def _memory_counts(memory):
    return {
        key: len(value) if isinstance(value, (dict, list)) else 0
        for key, value in memory.items()
    }

def get_discovery_memory_insights():
    memory = _memory()
    counts = _memory_counts(memory)
    return {
        "status": "SUCCESS",
        "storage": str(MEMORY_FILE),
        "counts": counts,
        "memory": memory
    }

def search_discovery_reports(query="", limit=20):
    query = str(query or "").strip().lower()
    limit = max(1, min(int(limit), 100))
    matches = []
    for report in _reports():
        searchable = json.dumps(report["data"], ensure_ascii=False).lower()
        if not query or query in searchable or query in report["filename"].lower():
            data = report["data"]
            matches.append({
                "filename": report["filename"],
                "modified": report["modified"],
                "status": data.get("status"),
                "total_stories": data.get("total_stories", 0),
                "opportunities": len(data.get("top_opportunities", [])),
                "report": data
            })
        if len(matches) >= limit:
            break
    return {"status": "SUCCESS", "count": len(matches), "reports": matches}

def get_signal_commander_insights():
    reports = _reports()
    latest = reports[0] if reports else None
    data = latest["data"] if latest else {}
    opportunities = data.get("top_opportunities", [])
    verified = data.get("verified_opportunities", [])
    tree = data.get("discovery_tree", {})
    cross = data.get("cross_category_intelligence", [])
    return {
        "status": "SUCCESS",
        "report_count": len(reports),
        "latest_report": latest["filename"] if latest else None,
        "latest_report_modified": latest["modified"] if latest else None,
        "latest_discovery_status": data.get("status", "NO_REPORT"),
        "total_stories": data.get("total_stories", 0),
        "ranked_opportunities": len(opportunities) if isinstance(opportunities, list) else 0,
        "verified_opportunities": len(verified) if isinstance(verified, list) else 0,
        "cross_category_findings": len(cross) if isinstance(cross, list) else 0,
        "discovery_tree_available": bool(tree),
        "publishing_enabled": False
    }

def audit_central_tool_registry():
    try:
        from tools.manager import TOOLS
        names = list(TOOLS.keys())
        duplicates = sorted({name for name in names if names.count(name) > 1})
        signal_tools = [n for n in names if "signal" in n.lower() or "discovery" in n.lower()]
        return {
            "status": "SUCCESS",
            "registered_tool_count": len(names),
            "duplicate_names": duplicates,
            "signal_commander_tools": sorted(signal_tools),
            "registry_names": sorted(names)
        }
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc)}

def get_intelligence_dashboard():
    memory = get_discovery_memory_insights()
    tasks = _tasks()
    statuses = Counter(str(t.get("status", "UNKNOWN")) for t in tasks)
    workloads = {}
    for task in tasks:
        aid = task.get("agent_id", "unassigned")
        item = workloads.setdefault(aid, {
            "agent_id": aid,
            "agent_name": task.get("agent_name", "Unknown"),
            "total": 0,
            "statuses": {}
        })
        item["total"] += 1
        state = str(task.get("status", "UNKNOWN"))
        item["statuses"][state] = item["statuses"].get(state, 0) + 1

    insights = get_signal_commander_insights()
    report_results = search_discovery_reports(limit=5)
    registry = audit_central_tool_registry()

    return {
        "status": "SUCCESS",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "discovery_memory": {
            "counts": memory["counts"],
            "storage": memory["storage"]
        },
        "signal_commander": insights,
        "agent_tasks": {
            "total": len(tasks),
            "status_counts": dict(statuses),
            "agent_workloads": list(workloads.values())
        },
        "latest_reports": [
            {
                "filename": r["filename"],
                "modified": r["modified"],
                "status": r["status"],
                "opportunities": r["opportunities"]
            }
            for r in report_results["reports"]
        ],
        "central_tool_registry": {
            "status": registry.get("status"),
            "registered_tool_count": registry.get("registered_tool_count", 0),
            "duplicate_names": registry.get("duplicate_names", []),
            "signal_commander_tools": registry.get("signal_commander_tools", [])
        },
        "external_actions_started": False
    }
