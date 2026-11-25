from agents.router import route_request
from agents.task_store import save_tasks
from skills.manager import read_skill


def dispatch_request(skill_name, user_request):
    if not isinstance(skill_name, str) or not skill_name.strip():
        raise ValueError("A valid skill name is required.")
    if not isinstance(user_request, str) or not user_request.strip():
        raise ValueError("A valid user request is required.")

    skill_name = skill_name.strip()
    route = route_request(skill_name)

    return {
        "agent_id": route["agent_id"],
        "agent_name": route["agent"],
        "skill": skill_name,
        "user_request": user_request.strip(),
        "instructions": read_skill(skill_name),
        "status": "READY",
    }


def dispatch_opportunity(opportunity):
    if not isinstance(opportunity, dict):
        raise ValueError("Opportunity must be a dictionary.")

    title = str(opportunity.get("title") or opportunity.get("name") or "").strip()
    if not title:
        raise ValueError("Opportunity must contain a title or name.")

    evidence = opportunity.get("evidence") or opportunity.get("description") or opportunity.get("body") or ""
    source = opportunity.get("url") or opportunity.get("href") or ""
    category = opportunity.get("category") or opportunity.get("niche") or "Unclassified"
    score = opportunity.get("score")

    request = (
        "Prepare an evidence-based intelligence brief for this discovered opportunity.\n"
        f"Title: {title[:300]}\n"
        f"Category: {str(category)[:120]}\n"
        f"Evidence: {str(evidence)[:4000]}\n"
        f"Source: {str(source)[:1000]}\n"
        f"Opportunity score: {score}\n\n"
        "Assess relevance, evidence quality, risks, uncertainties, timing and "
        "practical next research steps. Do not invent missing evidence."
    )

    task = dispatch_request("signal_commander", request)
    task["opportunity"] = {
        "title": title[:300],
        "category": str(category)[:120],
        "source": str(source)[:1000],
        "score": score,
    }
    task["handoff_type"] = "INTELLIGENCE_RESEARCH"
    return task


def dispatch_opportunities(opportunities, max_tasks=10):
    if not isinstance(opportunities, (list, tuple)):
        raise ValueError("Opportunities must be a list.")
    if not isinstance(max_tasks, int) or isinstance(max_tasks, bool) or not 1 <= max_tasks <= 20:
        raise ValueError("max_tasks must be between 1 and 20.")

    tasks = []
    errors = []

    for index, opportunity in enumerate(opportunities[:max_tasks]):
        try:
            tasks.append(dispatch_opportunity(opportunity))
        except (ValueError, TypeError) as exc:
            errors.append({"index": index, "error": str(exc)})

    archive = save_tasks(tasks) if tasks else {
        "status": "EMPTY",
        "tasks_saved": 0,
        "tasks": [],
    }

    return {
        "status": "READY" if tasks else "NO_VALID_TASKS",
        "tasks_created": len(tasks),
        "tasks": archive.get("tasks", tasks),
        "errors": errors,
        "archive_status": archive["status"],
        "tasks_archived": archive["tasks_saved"],
        "execution_started": False,
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
