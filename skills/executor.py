from skills.manager import list_skills
from tools.filesystem import list_files, read_file
from tools.web_research import fetch_page
from tools.approval import approve_tool_call
from tools.mcp_manager import MCPManager

from integrations.openmausbot.client import (
    list_tools as mcp_list_tools,
    call_tool as mcp_call_tool,
)


SKILL_EXECUTORS = {
    "file_management": {
        "list": list_files,
        "read": read_file,
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


async def execute_openmausbot(action, **kwargs):
    if action not in ("list_tools", "call_tool"):
        raise ValueError("Action not permitted for OpenMausBot.")

    server_name = kwargs.get("server_name")
    if not isinstance(server_name, str) or not server_name:
        raise ValueError("A valid MCP server name is required.")

    manager = MCPManager()
    config = manager.config["mcpServers"].get(server_name)

    if not isinstance(config, dict):
        raise ValueError("MCP server not found.")

    if action == "list_tools":
        approved = approve_tool_call(
            "mcp_list_tools", {"server": server_name}
        )
        tool_name = None
        arguments = {}
    else:
        tool_name = kwargs.get("tool_name")
        arguments = kwargs.get("arguments") or {}

        if not isinstance(tool_name, str) or not tool_name:
            raise ValueError("A valid MCP tool name is required.")

        if not isinstance(arguments, dict):
            raise ValueError("MCP arguments must be a dictionary.")

        approved = approve_tool_call(
            "mcp_call_tool",
            {
                "server": server_name,
                "tool": tool_name,
                "argument_keys": list(arguments.keys()),
            },
        )

    if not approved:
        return "MCP action cancelled. Permission denied."

    validation = manager.validate_server(server_name, approved=True)

    if validation["status"] != "VALID":
        raise PermissionError(validation["message"])

    transport_config = {
        **config,
        "type": "http" if validation["type"] == "HTTP" else "stdio",
    }

    if action == "list_tools":
        return await mcp_list_tools(transport_config)

    return await mcp_call_tool(
        transport_config,
        tool_name,
        arguments,
        approved=True,
    )


async def execute_skill_async(skill_name, action, **kwargs):
    if skill_name not in list_skills():
        raise ValueError("Unknown skill.")

    if skill_name == "openmausbot":
        return await execute_openmausbot(action, **kwargs)

    if skill_name == "web_research":
        if action != "fetch":
            raise ValueError("Action not permitted for this skill.")

        return await fetch_page(**kwargs)

    return execute_skill(skill_name, action, **kwargs)


if __name__ == "__main__":
    print("NEXUS AI SKILLS EXECUTION ENGINE")
    print("--------------------------------")
    print("Registered skills:", len(list_skills()))
    print("File Management: READY")
    print("Web Research: READY")
    print("OpenMausBot MCP: READY")
    print("MCP approval: REQUIRED")
