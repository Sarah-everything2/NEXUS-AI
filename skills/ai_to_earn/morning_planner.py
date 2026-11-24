"""NEXUS AI morning briefing and daily task planner."""
from datetime import datetime

TASKS = {
    "mining": "Monero mining (XMRig)",
    "trading": "MT5 Headway-Demo trading",
    "youtube": "Video clipping and YouTube content",
    "research": "Signal Commander trend research",
    "system": "System health and RAM monitoring",
}

def morning_briefing():
    now = datetime.now()
    return {
        "greeting": "Good morning. Let's plan your day.",
        "date": now.strftime("%A, %d %B %Y"),
        "time": now.strftime("%H:%M"),
        "tasks": TASKS,
        "rules": {
            "mining": "Requires hardware safety checks and your approval.",
            "trading": "HEADWAY DEMO ONLY. One daily plan approval starts automatic demo execution. No per-trade approval. Live accounts are blocked.",
            "youtube": "Publishing requires your approval.",
            "system": "Stop heavy tasks if system resources become unsafe.",
        },
    }

def daily_plan(selected_tasks=None):
    selected_tasks = selected_tasks or []
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "selected": {key: TASKS[key] for key in selected_tasks if key in TASKS},
        "real_trading": False,
        "requires_approval": True,
    }

def format_briefing():
    b = morning_briefing()
    lines = [
        "=" * 45,
        "       NEXUS AI - MORNING BRIEFING",
        "=" * 45,
        b["greeting"],
        "Date: " + b["date"],
        "Time: " + b["time"],
        "",
        "DAILY ACTIVITIES:",
    ]
    for key, task in b["tasks"].items():
        lines.append("  [ ] " + key.upper() + " - " + task)
    lines.extend([
        "",
        "SAFETY:",
        "  - MT5 trading: DEMO ONLY",
        "  - No real-money trading",
        "  - Mining: hardware checks required",
        "  - YouTube: approval required before publishing",
        "=" * 45,
    ])
    return "\n".join(lines)

if __name__ == "__main__":
    print(format_briefing())

