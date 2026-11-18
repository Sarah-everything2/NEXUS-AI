from brain.ollama_client import OllamaClient
from memory.store import save_message, get_recent_messages
from tools.manager import execute_tool, get_available_tools, get_mcp_servers
from tools.approval import approve_tool_call
from skills.manager import list_skills, read_skill
from agents.dispatcher import dispatch_request


class NexusAgent:

    def __init__(self):
        self.ai = OllamaClient()

    def build_system_context(self):

        skills = list_skills()
        skill_instructions = []

        for skill in skills:
            try:
                instructions = read_skill(skill)
                skill_instructions.append(
                    f"\n--- {skill.upper()} SKILL ---\n{instructions}"
                )
            except (ValueError, PermissionError):
                continue

        available_tools = get_available_tools()
        mcp_servers = get_mcp_servers()

        return f"""
You are NEXUS AI, a modular personal AI assistant.

YOUR RESPONSIBILITIES:
- Help the user operate all registered NEXUS AI skills.
- Understand requests and explain how to complete tasks.
- Be honest about available capabilities.
- Never claim an action was completed unless it actually was.
- Protect the user's files, accounts and financial assets.
- Require approval for consequential actions.

REGISTERED SKILLS:
{", ".join(skills)}

AVAILABLE TOOLS:
{", ".join(available_tools)}`n`nREGISTERED MCP SERVERS:`n{mcp_servers}

IMPORTANT:
A registered skill is an instruction module, not necessarily
an active integration. Do not pretend unavailable integrations
or services are connected.

SKILL INSTRUCTIONS:
{"".join(skill_instructions)}

SAFETY:
Never reveal passwords, private keys or recovery phrases.
Never execute financial transactions without approval.
Never bypass security restrictions.
"""

    async def ask(self, question):

        if not question.strip():
            raise ValueError("Question cannot be empty.")

        save_message("user", question)

        history = get_recent_messages(limit=20)

        messages = [
            {
                "role": "system",
                "content": self.build_system_context()
            }
        ] + history

        answer = await self.ai.generate(messages)

        save_message("assistant", answer)

        return answer

    async def ask_specialist(self, skill_name, question):

        if not question.strip():
            raise ValueError("Question cannot be empty.")

        task = dispatch_request(skill_name, question)

        system_message = f"""
You are {task['agent_name']} in NEXUS AI.

Your assigned skill is: {skill_name}

Follow these skill instructions:
{task['instructions']}

User request:
{question}

Be accurate. Never claim to have performed actions
that you have not actually performed.
Respect all NEXUS AI safety rules.
"""

        save_message("user", question)

        answer = await self.ai.generate([
            {
                "role": "system",
                "content": system_message
            },
            {
                "role": "user",
                "content": question
            }
        ])

        save_message("assistant", answer)

        return answer
    def available_tools(self):
        return get_available_tools()

    def available_skills(self):
        return list_skills()

    def load_skill(self, skill_name):
        return read_skill(skill_name)

    async def use_tool(self, tool_name, **kwargs):

        approved = approve_tool_call(tool_name, kwargs)

        if not approved:
            return "Action cancelled. Permission denied."

        return await execute_tool(tool_name, **kwargs)
