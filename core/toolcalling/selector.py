import json
from tools.manager import get_available_tools


class ToolSelector:

    def __init__(self, ai):
        self.ai = ai

    async def select_tools(self, question):

        available_tools = get_available_tools()

        prompt = f"""
You are the NEXUS AI tool selector.

User request:
{question}

Registered tools:
{available_tools}

Rules:
- Select only tools from the registered tools list.
- Never invent tool names.
- Never execute tools.
- Never perform financial transactions.
- Select no more than 2 tools.
- If no tool is needed, return an empty actions list.
- Arguments must be JSON objects.
- Return valid JSON only.

Format:
{{
    "actions": [
        {{
            "tool": "tool_name",
            "arguments": {{}}
        }}
    ]
}}
"""

        response = await self.ai.generate([
            {"role": "user", "content": prompt}
        ])

        try:
            data = json.loads(response)
        except (json.JSONDecodeError, TypeError):
            return []

        actions = data.get("actions", [])

        if not isinstance(actions, list):
            return []

        validated = []
        seen = set()

        for action in actions[:2]:

            if not isinstance(action, dict):
                continue

            tool = action.get("tool")
            arguments = action.get("arguments", {})

            if tool not in available_tools:
                continue

            if not isinstance(arguments, dict):
                continue

            key = (tool, json.dumps(arguments, sort_keys=True))

            if key in seen:
                continue

            seen.add(key)

            validated.append({
                "tool": tool,
                "arguments": arguments
            })

        return validated