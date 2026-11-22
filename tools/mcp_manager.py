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
        return {
            "status": "SUCCESS",
            "servers": [
                {
                    "name": name,
                    "type": "HTTP" if "url" in settings else "LOCAL",
                    "enabled": settings.get("enabled") is True
                }
                for name, settings in self.config["mcpServers"].items()
            ]
        }

    def validate_server(self, name, approved=False):
        servers = self.config["mcpServers"]

        if name not in servers:
            return {"status": "ERROR", "message": "Server not found."}

        settings = servers[name]

        if not isinstance(settings, dict):
            return {"status": "ERROR", "message": "Invalid server settings."}

        if settings.get("enabled") is not True:
            return {"status": "BLOCKED", "message": "Server is disabled."}

        if "url" in settings:
            if not settings["url"].startswith("https://"):
                return {"status": "BLOCKED", "message": "HTTPS required."}

            return {"status": "VALID", "type": "HTTP"}

        if "command" in settings:
            if not approved:
                return {
                    "status": "BLOCKED",
                    "message": "Explicit security approval required."
                }

            return {"status": "VALID", "type": "STDIO"}

        return {"status": "ERROR", "message": "Unsupported configuration."}


if __name__ == "__main__":
    manager = MCPManager()
    print("NEXUS AI MCP MANAGER")
    print(json.dumps(manager.list_servers(), indent=4))
    print("External servers remain disabled by default.")
