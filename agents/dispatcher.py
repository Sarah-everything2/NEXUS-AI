from agents.router import route_request
from skills.manager import read_skill


def dispatch_request(skill_name, user_request):

    route = route_request(skill_name)
    instructions = read_skill(skill_name)

    return {
        "agent_id": route["agent_id"],
        "agent_name": route["agent"],
        "skill": skill_name,
        "user_request": user_request,
        "instructions": instructions,
        "status": "READY"
    }


if __name__ == "__main__":

    result = dispatch_request(
        "trading",
        "Analyse the current market conditions."
    )

    print("NEXUS AI AGENT DISPATCHER")
    print("-------------------------")
    print("Agent:", result["agent_name"])
    print("Skill:", result["skill"])
    print("Status:", result["status"])
