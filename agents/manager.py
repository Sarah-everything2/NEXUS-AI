from core.settings import load_settings


AGENTS = {
    "research_agent": {
        "name": "Research Agent",
        "skills": ["osint", "web_research", "web_scraping"]
    },

    "trading_agent": {
        "name": "Trading Agent",
        "skills": ["trading", "stock_intelligence"]
    },

    "content_agent": {
        "name": "Content Agent",
        "skills": ["video_clipping", "youtube_automation"]
    },

    "automation_agent": {
        "name": "Automation Agent",
        "skills": [
            "social_media",
            "airdrop_manager",
            "ai_to_earn"
        ]
    },

    "intelligence_agent": {
        "name": "Intelligence Agent",
        "skills": [
            "mining",
            "memecoin_intelligence",
            "nft_intelligence"
        ]
    }
}


def list_agents():
    settings = load_settings()
    enabled = settings.get("agents", [])

    return {
        agent_id: details
        for agent_id, details in AGENTS.items()
        if agent_id in enabled
    }


def get_agent(agent_id):
    agents = list_agents()

    if agent_id not in agents:
        raise ValueError(f"Unknown or disabled agent: {agent_id}")

    return agents[agent_id]


if __name__ == "__main__":
    print("NEXUS AI MULTI-AGENT MANAGER")
    print("----------------------------")

    for agent_id, details in list_agents().items():
        print(f"\n{details['name']}")
        print("ID:", agent_id)
        print("Skills:", ", ".join(details["skills"]))

    print("\nRegistered agents:", len(list_agents()))
    print("Status: READY")