import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INTEGRATIONS = ROOT / "integrations"
REPORT = ROOT / "config" / "video_account_discovery.json"

TERMS = (
    "oauth", "token", "credential", "youtube",
    "tiktok", "instagram", "refresh", "account"
)


def discover_accounts():
    modules = []
    functions = []

    for path in INTEGRATIONS.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue

        relative = str(path.relative_to(ROOT)).lower()

        if not any(term in relative for term in TERMS):
            continue

        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue

        names = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.append(node.name)

        modules.append(str(path.relative_to(ROOT)))

        for name in names:
            if any(term in name.lower() for term in TERMS):
                functions.append({
                    "module": str(path.relative_to(ROOT)),
                    "function": name
                })

    result = {
        "modules": modules,
        "functions": functions,
        "secrets_read": False
    }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
