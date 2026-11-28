"""Fail-closed verifiers for bounded, read-only filesystem operations."""

import re



def _operations(execution):
    if not isinstance(execution, dict) or execution.get("success") is not True:
        return []
    results = execution.get("results", [])
    return results if isinstance(results, list) else []


def _normal_path(value):
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip().strip("\"'").replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    if value in ("", "."):
        return "."
    parts = value.split("/")
    if value.startswith("/") or ":" in parts[0] or any(x in ("..", "") for x in parts):
        return None
    return "/".join(parts).casefold()


def _task_mentions_path(task, path):
    if not isinstance(task, str) or not path or path == ".":
        return False

    normalized_task = task.replace("\\", "/").casefold()
    escaped = re.escape(path.casefold())

    # Require the complete path, not a substring of another path.
    pattern = r"(?<![a-z0-9_./-])" + escaped + r"(?![a-z0-9_./-])"
    return re.search(pattern, normalized_task) is not None


def verify_list_files(task, execution):
    if not isinstance(task, str):
        return {"verified": False, "reason": "Invalid task."}

    task_lower = task.casefold()
    if not any(x in task_lower for x in ("list", "show", "display", "enumerate")):
        return {"verified": False, "reason": "Task is not a directory-listing request."}
    if not any(x in task_lower for x in ("file", "folder", "directory", "workspace")):
        return {"verified": False, "reason": "Task does not identify a filesystem listing."}

    operations = _operations(execution)
    if len(operations) != 1:
        return {"verified": False, "reason": "Expected exactly one successful listing operation."}

    operation = operations[0]
    if not isinstance(operation, dict) or operation.get("tool") != "list_files":
        return {"verified": False, "reason": "Listing tool did not match."}

    arguments = operation.get("arguments")
    if not isinstance(arguments, dict):
        return {"verified": False, "reason": "Actual tool arguments are unavailable."}

    path = _normal_path(arguments.get("relative_path", "."))
    if path is None:
        return {"verified": False, "reason": "Unsafe or invalid listing path."}
    if path == ".":
        if not any(x in task_lower for x in ("workspace", "files", "folders", "directories")):
            return {"verified": False, "reason": "Default workspace listing was not requested."}
    elif not _task_mentions_path(task, path):
        return {"verified": False, "reason": "Listed path does not match the task."}

    if operation.get("error"):
        return {"verified": False, "reason": "Listing operation returned an error."}

    result = operation.get("result")
    if not isinstance(result, list):
        return {"verified": False, "reason": "Listing result has an unexpected format."}
    if not all(
        isinstance(entry, dict)
        and isinstance(entry.get("name"), str)
        and entry.get("type") in ("file", "directory")
        for entry in result
    ):
        return {"verified": False, "reason": "Listing entries failed validation."}

    files = sum(entry["type"] == "file" for entry in result)
    directories = sum(entry["type"] == "directory" for entry in result)
    return {
        "verified": True,
        "trusted_source": True,
        "semantic_success_verified": True,
        "verification_scope": "workspace_directory_listing",
        "learning_target": {
            "operation": "list_files",
            "success": True,
            "entry_count": len(result),
            "file_count": files,
            "directory_count": directories,
        },
    }


def verify_read_file(task, execution):
    if not isinstance(task, str):
        return {"verified": False, "reason": "Invalid task."}

    task_lower = task.casefold()
    if not any(x in task_lower for x in ("read", "display", "show", "view", "open")):
        return {"verified": False, "reason": "Task is not a file-reading request."}
    if not any(x in task_lower for x in ("file", "contents", "content", "text")):
        return {"verified": False, "reason": "Task does not identify file content."}

    operations = _operations(execution)
    if len(operations) != 1:
        return {"verified": False, "reason": "Expected exactly one successful read operation."}

    operation = operations[0]
    if not isinstance(operation, dict) or operation.get("tool") != "read_file":
        return {"verified": False, "reason": "Read tool did not match."}

    arguments = operation.get("arguments")
    if not isinstance(arguments, dict):
        return {"verified": False, "reason": "Actual tool arguments are unavailable."}

    path = _normal_path(arguments.get("relative_path"))
    if path is None or path == ".":
        return {"verified": False, "reason": "A valid relative file path is required."}
    if not _task_mentions_path(task, path):
        return {"verified": False, "reason": "Read path does not match the task."}

    if operation.get("error"):
        return {"verified": False, "reason": "Read operation returned an error."}

    result = operation.get("result")
    if not isinstance(result, str):
        return {"verified": False, "reason": "Read result has an unexpected format."}

    return {
        "verified": True,
        "trusted_source": True,
        "semantic_success_verified": True,
        "verification_scope": "workspace_file_read",
        "learning_target": {
            "operation": "read_file",
            "success": True,
            "character_count": len(result),
            "nonempty": bool(result),
        },
    }


def register_filesystem_verifiers(registry):
    registered = set(registry.names())

    verifiers = {
        "filesystem.list_files": verify_list_files,
        "filesystem.read_file": verify_read_file,
    }

    for name, verifier in verifiers.items():
        if name not in registered:
            registry.register(name, verifier)

    return sorted(verifiers)
