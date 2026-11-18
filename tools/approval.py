from core.settings import load_settings


def approve_tool_call(tool_name, arguments):

    settings = load_settings()

    print("\nNEXUS AI PERMISSION REQUEST")
    print("---------------------------")
    print("Requested tool:", tool_name)
    print("Arguments:", arguments)

    # Block file deletion unless explicitly enabled
    if tool_name == "delete_file":
        if not settings.get("allow_file_deletion", False):
            print("BLOCKED: File deletion is disabled in settings.")
            return False

        confirmation = input(
            "This action deletes a file. Type DELETE to confirm: "
        )
        return confirmation == "DELETE"

    # Require approval for other tools
    if settings.get("require_approval", True):
        confirmation = input(
            "Allow this action? Type YES to confirm: "
        )
        return confirmation == "YES"

    return True


if __name__ == "__main__":
    print("NEXUS AI PERMISSION MANAGER")
    print("Status: READY")