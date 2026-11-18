import inspect

from tools.filesystem import (
    list_files,
    read_file,
    write_file,
    delete_file
)

from tools.web_research import fetch_page
from tools.mcp_manager import MCPManager
from tools.github_tools import github_call, ALLOWED_TOOLS


TOOLS = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "delete_file": delete_file,
    "web_research": fetch_page
}

# GITHUB MCP TOOLS

def make_github_executor(mcp_tool_name):
    async def execute(**kwargs):
        return await github_call(mcp_tool_name, kwargs)
    return execute


for github_name in ALLOWED_TOOLS:
    TOOLS[f"github_{github_name}"] = make_github_executor(github_name)



def get_available_tools():
    return list(TOOLS.keys())


def get_mcp_servers():
    return MCPManager().list_servers()


async def execute_tool(tool_name, **kwargs):
    if tool_name not in TOOLS:
        raise ValueError(f"Unknown tool: {tool_name}")

    tool = TOOLS[tool_name]
    result = tool(**kwargs)

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