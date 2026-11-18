from agents.manager import get_agent, list_agents


def route_request(skill_name):

    for agent_id, details in list_agents().items():

        if skill_name in details["skills"]:
            return {
                "agent_id": agent_id,
                "agent": details["name"],
                "skill": skill_name
            }

    raise ValueError(
        f"No registered agent supports skill: {skill_name}"
    )


if __name__ == "__main__":

    print("NEXUS AI AGENT ROUTER")
    print("---------------------")

    test_skills = [
        "osint",
        "trading",
        "video_clipping",
        "airdrop_manager",
        "memecoin_intelligence"
    ]

    for skill in test_skills:
        print(skill, "->", route_request(skill))

    print("Status: READY")
