import sys
from core.settings import load_settings
from tools.github_tools import READ_ONLY_TOOLS


# Tools permitted to run autonomously.
AUTONOMOUS_SAFE_TOOLS = {
    "list_files",
    "read_file",
    "web_research",
    "trend_discovery",
    "xmrig_status",
    "xmrig_health",
    "xmrig_logs",
    "xmrig_recovery_check",
    "mt5_get_account",
    "mt5_get_price",
    "mt5_get_positions",
    "mt5_get_history",
    "mt5_get_strategy_signal",
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



def _confirm_interactively(prompt, expected):
    """Never block a hosted service waiting for terminal input."""
    try:
        if not sys.stdin or not sys.stdin.isatty():
            print("BLOCKED: Interactive approval is unavailable.")
            return False
        return input(prompt) == expected
    except (EOFError, OSError):
        return False


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

        return _confirm_interactively(
            "Type DELETE to confirm file deletion: ",
            "DELETE"
        )

    # Safe tools can operate autonomously.
    if settings.get("autonomous_mode", False):

        if (
            tool_name in AUTONOMOUS_SAFE_TOOLS
            or (
                tool_name.startswith("github_")
                and tool_name.removeprefix("github_") in READ_ONLY_TOOLS
            )
        ):
            print("AUTONOMOUS MODE: Safe operation approved.")
            return True

    # All other operations require explicit approval.
    print("Arguments:", arguments)

    return _confirm_interactively(
        "Allow this action? Type YES to confirm: ",
        "YES"
    )


if __name__ == "__main__":
    print("NEXUS AI PERMISSION MANAGER")
    print("Status: READY")