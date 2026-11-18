from pathlib import Path

SKILLS_DIR = Path(__file__).parent.resolve()


def list_skills():
    skills = []

    for item in sorted(SKILLS_DIR.iterdir()):
        if item.is_dir() and (item / "SKILL.md").is_file():
            skills.append(item.name)

    return skills


def read_skill(skill_name):
    if not skill_name.replace("_", "").replace("-", "").isalnum():
        raise ValueError("Invalid skill name.")

    skill_file = (SKILLS_DIR / skill_name / "SKILL.md").resolve()

    if not skill_file.is_relative_to(SKILLS_DIR):
        raise PermissionError("Access outside skills directory prohibited.")

    if not skill_file.is_file():
        raise ValueError("Skill does not exist.")

    if skill_file.stat().st_size > 100_000:
        raise ValueError("Skill file exceeds size limit.")

    return skill_file.read_text(encoding="utf-8")


if __name__ == "__main__":
    print("NEXUS AI SKILLS MANAGER")
    print("-----------------------")
    print("Available skills:", list_skills())
    print("Status: READY")
