import asyncio

from skills.manager import list_skills
from tools.filesystem import list_files, read_file
from tools.web_research import fetch_page


SKILL_EXECUTORS = {
    "file_management": {
        "list": list_files,
        "read": read_file
    }
}


def execute_skill(skill_name, action, **kwargs):

    if skill_name not in list_skills():
        raise ValueError("Unknown skill.")

    if skill_name not in SKILL_EXECUTORS:
        raise NotImplementedError(
            f"{skill_name} requires asynchronous execution or is not operational."
        )

    actions = SKILL_EXECUTORS[skill_name]

    if action not in actions:
        raise ValueError("Action not permitted for this skill.")

    return actions[action](**kwargs)


async def execute_skill_async(skill_name, action, **kwargs):

    if skill_name not in list_skills():
        raise ValueError("Unknown skill.")

    if skill_name == "web_research":

        if action != "fetch":
            raise ValueError("Action not permitted for this skill.")

        return await fetch_page(**kwargs)

    return execute_skill(skill_name, action, **kwargs)


if __name__ == "__main__":

    print("NEXUS AI SKILLS EXECUTION ENGINE")
    print("--------------------------------")
    print("Registered skills:", len(list_skills()))
    print("Operational skills:")
    print("- File Management")
    print("- Web Research")
    print("Web Research action: fetch")
    print("Status: READY")