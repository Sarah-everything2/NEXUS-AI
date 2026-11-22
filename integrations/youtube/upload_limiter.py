"""Local daily YouTube upload limiter."""
import json
from datetime import date
from pathlib import Path

STATE_FILE = Path(__file__).with_name("upload_state.json")


def load_state():
    if not STATE_FILE.exists():
        return {"date": date.today().isoformat(), "uploads": 0}

    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8-sig"))
        if state.get("date") != date.today().isoformat():
            return {"date": date.today().isoformat(), "uploads": 0}
        return state
    except (ValueError, OSError):
        return {"date": date.today().isoformat(), "uploads": 0}


def can_upload(limit=3):
    return load_state()["uploads"] < limit


def record_upload(limit=3):
    state = load_state()
    if state["uploads"] >= limit:
        raise PermissionError("Daily YouTube upload limit reached.")

    state["uploads"] += 1
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state
