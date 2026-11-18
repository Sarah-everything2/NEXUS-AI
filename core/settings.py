import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.json"

DEFAULT_SETTINGS = {
    "app_name": "NEXUS AI",
    "version": "0.2.0",

    "ai_provider": "ollama",
    "ollama_url": "http://localhost:11434",
    "model": "",

    "memory_enabled": True,

    "autonomous_mode": False,
    "require_approval": True,
    "allow_file_deletion": False,
    "workspace_only": True,

    "agents": [
        "research_agent",
        "trading_agent",
        "content_agent",
        "automation_agent",
        "intelligence_agent"
    ],

    "enabled_skills": [
        "file_management",
        "web_research",
        "web_scraping",
        "mining",
        "trading",
        "video_clipping",
        "youtube_automation",
        "social_media",
        "airdrop_manager",
        "ai_to_earn",
        "osint",
        "memecoin_intelligence",
        "nft_intelligence",
        "stock_intelligence"
    ],

    "safety": {
        "require_trade_approval": True,
        "require_wallet_approval": True,
        "require_publishing_approval": True,
        "protect_private_keys": True,
        "protect_credentials": True
    }
}


def load_settings():
    if not CONFIG_PATH.exists():
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        settings = json.load(file)

    merged = {**DEFAULT_SETTINGS, **settings}

    merged["safety"] = {
        **DEFAULT_SETTINGS["safety"],
        **settings.get("safety", {})
    }

    return merged


def save_settings(settings):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(CONFIG_PATH, "w", encoding="utf-8") as file:
        json.dump(settings, file, indent=4)


if __name__ == "__main__":
    settings = load_settings()

    print("NEXUS AI CENTRAL CONFIGURATION")
    print("--------------------------------")

    print("Version:", settings["version"])
    print("AI Provider:", settings["ai_provider"])
    print("Memory:", settings["memory_enabled"])
    print("Registered Skills:", len(settings["enabled_skills"]))
    print("Registered Agents:", len(settings["agents"]))
    print("Autonomous Mode:", settings["autonomous_mode"])
    print("Approval Required:", settings["require_approval"])

    print("Status: READY")