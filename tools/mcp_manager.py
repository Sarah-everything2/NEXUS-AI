import json
from pathlib import Path


CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "mcp_servers.json"


class MCPManager:
    def __init__(self):
        self.config = self.load_config()

    def load_config(self):
        if not CONFIG_FILE.exists():
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(
                json.dumps({"mcpServers": {}}, indent=4),
                encoding="utf-8"
            )

        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raise ValueError("MCP configuration contains invalid JSON.")

        if not isinstance(data.get("mcpServers"), dict):
            raise ValueError("Invalid MCP configuration structure.")

        return data

    def list_servers(self):
        servers = self.config["mcpServers"]

        if not servers:
            return {"status": "SUCCESS", "servers": []}

        return {
            "status": "SUCCESS",
            "servers": [
                {
                    "name": name,
                    "type": "HTTP" if "url" in settings else "LOCAL",
                    "enabled": False
                }
                for name, settings in servers.items()
            ]
        }

    def validate_server(self, name):
        servers = self.config["mcpServers"]

        if name not in servers:
            return {"status": "ERROR", "message": "Server not found."}

        settings = servers[name]

        if not isinstance(settings, dict):
            return {"status": "ERROR", "message": "Invalid server settings."}

        if "url" in settings:
            if not settings["url"].startswith("https://"):
                return {
                    "status": "BLOCKED",
                    "message": "Only HTTPS MCP servers are permitted."
                }

            return {"status": "VALID", "type": "HTTP"}

        if "command" in settings:
            return {
                "status": "BLOCKED",
                "message": "Local command execution requires security approval."
            }

        return {"status": "ERROR", "message": "Unsupported server configuration."}


if __name__ == "__main__":
    manager = MCPManager()

    print("NEXUS AI MCP MANAGER")
    print("-------------------")
    print(json.dumps(manager.list_servers(), indent=4))
    print("\nMCP manager ready.")
    print("External servers remain disabled.")