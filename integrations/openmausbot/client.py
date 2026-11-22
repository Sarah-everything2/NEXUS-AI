from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport


def build_transport(config: dict[str, Any]):
    if not isinstance(config, dict) or config.get("enabled") is not True:
        raise ValueError("MCP server is missing or disabled.")

    if config.get("type") == "http":
        url = config.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise ValueError("A valid HTTP MCP URL is required.")
        return StreamableHttpTransport(
            url=url,
            headers=config.get("headers") or {},
        )

    command = config.get("command")
    args = config.get("args") or []
    if not isinstance(command, str) or not isinstance(args, list):
        raise ValueError("Invalid STDIO MCP configuration.")

    return StdioTransport(
        command=command,
        args=args,
        env=config.get("env") or {},
    )


async def list_tools(config: dict[str, Any]):
    async with Client(build_transport(config)) as client:
        return await client.list_tools()


async def call_tool(
    config: dict[str, Any],
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    *,
    approved: bool = False,
):
    if not approved:
        raise PermissionError("Human approval is required to execute MCP tools.")

    if not tool_name or not isinstance(tool_name, str):
        raise ValueError("A valid tool name is required.")

    async with Client(build_transport(config)) as client:
        return await client.call_tool(tool_name, arguments or {})
