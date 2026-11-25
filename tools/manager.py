import inspect
import inspect

from tools.filesystem import list_files, read_file, write_file, delete_file
from tools.web_research import fetch_page
from tools.trend_discovery import discover_trends
from tools.mcp_manager import MCPManager
from tools.github_tools import github_call, ALLOWED_TOOLS
from tools.approval import approve_tool_call

from integrations.mt5.client import (
    get_account as mt5_get_account,
    get_price as mt5_get_price,
    get_positions as mt5_get_positions,
    get_history as mt5_get_history,
    get_strategy_signal as mt5_get_strategy_signal,
)
from integrations.openmausbot.client import (
    list_tools as mcp_list_tools,
    call_tool as mcp_call_tool,
)


TOOLS = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "delete_file": delete_file,
    "web_research": fetch_page,
    "trend_discovery": discover_trends,
}

TOOLS.update({
    "mt5_get_account": mt5_get_account,
    "mt5_get_price": mt5_get_price,
    "mt5_get_positions": mt5_get_positions,
    "mt5_get_history": mt5_get_history,
    "mt5_get_strategy_signal": mt5_get_strategy_signal,
})

def make_github_executor(mcp_tool_name):
    async def execute(**kwargs):
        registered_name = f"github_{mcp_tool_name}"
        approved = approve_tool_call(registered_name, kwargs)

        if not approved:
            return "GitHub action cancelled. Permission denied."

        return await github_call(mcp_tool_name, kwargs)
    return execute


for github_name in ALLOWED_TOOLS:
    TOOLS[f"github_{github_name}"] = make_github_executor(github_name)


async def execute_mcp_list_tools(server_name, **kwargs):
    approved = approve_tool_call(
        "mcp_list_tools",
        {"server": server_name}
    )

    if not approved:
        return "MCP action cancelled. Permission denied."

    manager = MCPManager()
    validation = manager.validate_server(server_name, approved=True)

    if validation["status"] != "VALID":
        raise PermissionError(validation["message"])

    config = manager.config["mcpServers"][server_name]

    transport_config = {
        **config,
        "type": "http" if validation["type"] == "HTTP" else "stdio",
    }

    return await mcp_list_tools(transport_config)


async def execute_mcp_call_tool(
    server_name,
    tool_name,
    arguments=None,
    **kwargs
):
    if not isinstance(tool_name, str) or not tool_name:
        raise ValueError("A valid MCP tool name is required.")

    if arguments is not None and not isinstance(arguments, dict):
        raise ValueError("MCP arguments must be a dictionary.")

    approved = approve_tool_call(
        "mcp_call_tool",
        {
            "server": server_name,
            "tool": tool_name,
            "argument_keys": list((arguments or {}).keys()),
        }
    )

    if not approved:
        return "MCP action cancelled. Permission denied."

    manager = MCPManager()
    validation = manager.validate_server(server_name, approved=True)

    if validation["status"] != "VALID":
        raise PermissionError(validation["message"])

    config = manager.config["mcpServers"][server_name]

    transport_config = {
        **config,
        "type": "http" if validation["type"] == "HTTP" else "stdio",
    }

    return await mcp_call_tool(
        transport_config,
        tool_name,
        arguments or {},
        approved=True,
    )


TOOLS["mcp_list_tools"] = execute_mcp_list_tools
TOOLS["mcp_call_tool"] = execute_mcp_call_tool



from tools.xmrig_tools import (
    xmrig_status, xmrig_health, xmrig_logs,
    xmrig_configure_pool, xmrig_start, xmrig_stop, xmrig_recovery_check,
)

TOOLS.update({
    "xmrig_status": xmrig_status,
    "xmrig_health": xmrig_health,
    "xmrig_logs": xmrig_logs,
    "xmrig_configure_pool": xmrig_configure_pool,
    "xmrig_start": xmrig_start,
    "xmrig_stop": xmrig_stop,
    "xmrig_recovery_check": xmrig_recovery_check,
})

from integrations.video_clipping.engine import (
    probe_video,
    extract_clip,
    create_vertical_short,
)

TOOLS.update({
    "video_probe": probe_video,
    "video_extract_clip": extract_clip,
    "video_create_vertical_short": create_vertical_short,
})


from integrations.video_clipping.engine import create_subtitles

TOOLS["video_create_subtitles"] = create_subtitles


from integrations.video_clipping.engine import burn_subtitles

TOOLS["video_burn_subtitles"] = burn_subtitles
from integrations.video_clipping.engine import detect_highlights

TOOLS["video_detect_highlights"] = detect_highlights


def get_available_tools():
    return list(TOOLS.keys())


def get_mcp_servers():
    return MCPManager().list_servers()


async def execute_tool(registered_tool_name, **kwargs):
    if registered_tool_name not in TOOLS:
        raise ValueError(f"Unknown tool: {registered_tool_name}")

    result = TOOLS[registered_tool_name](**kwargs)

    if inspect.isawaitable(result):
        result = await result

    return result

if __name__ == "__main__":
    print("NEXUS AI TOOL EXECUTION ENGINE")
    print("--------------------------------")

    print("\nAVAILABLE TOOLS:")
    for tool in get_available_tools():
        print("-", tool)

    print("\nMCP CONNECTIONS:")
    print(get_mcp_servers())

    print("\nStatus: READY")

from integrations.youtube.tools import (
    youtube_status,
    youtube_channel,
    youtube_controls,
    youtube_upload,
    youtube_upload_autonomous,
)

TOOLS.update({
    "youtube_status": youtube_status,
    "youtube_channel": youtube_channel,
    "youtube_controls": youtube_controls,
    "youtube_upload": youtube_upload,
    "youtube_upload_autonomous": youtube_upload_autonomous,
})





from integrations.video_clipping.engine import transcribe_video

TOOLS["video_transcribe"] = transcribe_video

from integrations.x_platform.tools import (
    x_status,
    x_account,
    x_analytics,
)

TOOLS.update({
    "x_status": x_status,
    "x_account": x_account,
    "x_analytics": x_analytics,
})


from integrations.x_platform.tools import (
    x_search_trends,
    x_account_timeline,
)

TOOLS.update({
    "x_search_trends": x_search_trends,
    "x_account_timeline": x_account_timeline,
})


from integrations.x_platform.tools import x_post, x_thread

TOOLS.update({
    "x_post": x_post,
    "x_thread": x_thread,
})

# NEXUS X Growth Agent
import skills.x_growth.tool_registration



# Signal Commander — unified research and opportunity discovery
from skills.signal_commander.discovery_orchestrator import run_discovery


async def signal_commander_discover(root_niche="Artificial Intelligence"):
    if not isinstance(root_niche, str) or not root_niche.strip():
        raise ValueError("A valid root niche is required.")
    if len(root_niche) > 120:
        raise ValueError("Root niche must not exceed 120 characters.")
    return await run_discovery(root_niche=root_niche.strip())


TOOLS["signal_commander_discover"] = signal_commander_discover

# NEXUS persistent intelligence task management
from agents.task_store import get_tasks, update_task

def nexus_list_agent_tasks(status=None, limit=100):
    return get_tasks(status=status, limit=limit)

def nexus_update_agent_task(task_id, status):
    return update_task(task_id, status)

def nexus_agent_workload():
    records = get_tasks(limit=1000)["tasks"]
    workload = {}
    for task in records:
        agent_id = task.get("agent_id", "unknown")
        entry = workload.setdefault(agent_id, {
            "agent_id": agent_id,
            "agent_name": task.get("agent_name", "Unknown"),
            "total": 0,
            "statuses": {}
        })
        entry["total"] += 1
        current = task.get("status", "UNKNOWN")
        entry["statuses"][current] = entry["statuses"].get(current, 0) + 1
    return {"status": "SUCCESS", "total_tasks": len(records),
            "agent_workloads": list(workload.values())}

TOOLS["nexus_list_agent_tasks"] = nexus_list_agent_tasks
TOOLS["nexus_update_agent_task"] = nexus_update_agent_task
TOOLS["nexus_agent_workload"] = nexus_agent_workload

# SIGNAL_COMMANDER_INTELLIGENCE_TOOLS
from skills.signal_commander.intelligence_dashboard import (
    get_intelligence_dashboard,
    get_discovery_memory_insights,
    get_signal_commander_insights,
    search_discovery_reports,
    audit_central_tool_registry,
)

TOOLS["signal_commander_dashboard"] = get_intelligence_dashboard
TOOLS["signal_commander_memory"] = get_discovery_memory_insights
TOOLS["signal_commander_insights"] = get_signal_commander_insights
TOOLS["signal_commander_report_search"] = search_discovery_reports
TOOLS["signal_commander_registry_audit"] = audit_central_tool_registry