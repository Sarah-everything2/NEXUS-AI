from core.settings import load_settings


# Tools permitted to run autonomously.
AUTONOMOUS_SAFE_TOOLS = {
    "list_files",
    "read_file",
    "web_research",
    "trend_discovery",
    "video_probe",
    "video_transcribe",
    "video_detect_highlights",
    "video_extract_clip",
    "video_create_vertical_short",
    "video_create_subtitles",
    "video_burn_subtitles",
    "youtube_status",
    "youtube_channel",
    "youtube_controls",
    "x_status",
    "x_account",
    "x_analytics",
    "x_search_trends",
    "x_account_timeline",
}


def approve_tool_call(tool_name, arguments):

    settings = load_settings()

    print("\nNEXUS AI PERMISSION MANAGER")
    print("---------------------------")
    print("Requested tool:", tool_name)

    # File deletion always requires explicit permission.
    if tool_name == "delete_file":

        if not settings.get("allow_file_deletion", False):
            print("BLOCKED: File deletion is disabled.")
            return False

        confirmation = input(
            "Type DELETE to confirm file deletion: "
        )

        return confirmation == "DELETE"

    # Safe tools can operate autonomously.
    if settings.get("autonomous_mode", False):

        if (
            tool_name in AUTONOMOUS_SAFE_TOOLS
            or tool_name.startswith("github_")
        ):
            print("AUTONOMOUS MODE: Safe operation approved.")
            return True

    # All other operations require explicit approval.
    print("Arguments:", arguments)

    confirmation = input(
        "Allow this action? Type YES to confirm: "
    )

    return confirmation == "YES"


if __name__ == "__main__":
    print("NEXUS AI PERMISSION MANAGER")
    print("Status: READY")