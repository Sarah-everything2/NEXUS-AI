import json
import os
from pathlib import Path
from fastmcp import Client

CONFIG = Path(__file__).resolve().parent.parent / "config" / "mcp_servers.json"

ALLOWED_TOOLS = {
    "get_commit", "get_file_contents", "get_label",
    "get_latest_release", "get_me", "get_release_by_tag",
    "get_tag", "get_team_members", "get_teams",
    "issue_read", "list_branches", "list_commits",
    "list_issue_fields", "list_issue_types", "list_issues",
    "list_pull_requests", "list_releases",
    "list_repository_collaborators", "list_tags",
    "pull_request_read", "search_code", "search_commits",
    "search_issues", "search_pull_requests",
    "search_repositories", "search_users", "ui_get"
}

async def github_call(tool_name, arguments):
    if tool_name not in ALLOWED_TOOLS:
        raise PermissionError("GitHub tool not allowed.")

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    server = config["mcpServers"]["github"]
    token = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("GitHub token is not loaded in this PowerShell session.")
    server["env"] = {"GITHUB_PERSONAL_ACCESS_TOKEN": token}

    async with Client({"mcpServers": {"github": server}}) as client:
        async def skip_schema_validation(name, result):
            return None

        client.session.validate_tool_result = skip_schema_validation

        return await client.call_tool_mcp(tool_name, arguments)