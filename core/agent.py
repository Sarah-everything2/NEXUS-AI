import json
from core.settings import load_settings
from brain.ollama_client import OllamaClient
from memory.store import save_message, get_recent_messages
from tools.manager import execute_tool, get_available_tools, get_mcp_servers
from tools.approval import approve_tool_call
from skills.manager import list_skills, read_skill
from agents.dispatcher import dispatch_request
from core.toolcalling.selector import ToolSelector
from integrations.youtube.upload import load_config
class NexusAgent:

    def __init__(self):
        self.ai = OllamaClient()
        self.tool_selector = ToolSelector(self.ai)
    async def run_autonomous_task(self, question):

        settings = load_settings()

        if not settings.get("autonomous_mode", False):
            return None

        safe_tools = [
            "list_files",
            "read_file",
            "web_research",
            "trend_discovery",
            "signal_commander_discover", "signal_commander_dashboard", "signal_commander_memory", "signal_commander_insights", "signal_commander_report_search", "signal_commander_registry_audit",
            "xmrig_status",
            "xmrig_health",
            "xmrig_logs",
            "xmrig_recovery_check",
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
            "mt5_get_account",
            "mt5_get_price",
            "mt5_get_positions",
            "mt5_get_history",
            "mt5_get_strategy_signal",
        ]

        youtube_config = load_config()
        if youtube_config.get("allow_autonomous_private_uploads", False):
            safe_tools.append("youtube_upload_autonomous")

        safe_tools += [
            tool for tool in get_available_tools()
            if tool.startswith("github_")
        ]

        prompt = f"""
You are the NEXUS AI autonomous task planner.

Available safe tools:
{safe_tools}

User request:
{question}

Rules:
- Select tools only when necessary.
- Use no more than 3 actions.
- Only use tools from the available safe tools list.
- Never select write_file or delete_file.
- Signal Commander is research-only: it discovers and ranks opportunities, verifies available evidence and saves reports. It must never publish, trade, mine or execute external actions.
- Never perform financial transactions.
- Never invent tool names.
- If no tool is needed, return an empty actions list.

Return ONLY valid JSON in this format:
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
            plan = json.loads(response)
        except json.JSONDecodeError:
            return None

        actions = plan.get("actions", [])

        if not isinstance(actions, list):
            return None

        results = []
        executed_tools = set()

        for action in actions[:3]:

            if not isinstance(action, dict):
                continue

            tool_name = action.get("tool")
            arguments = action.get("arguments", {})

            if tool_name not in safe_tools:
                continue

            if not isinstance(arguments, dict):
                continue

            tool_key = (tool_name, json.dumps(arguments, sort_keys=True))

            if tool_key in executed_tools:
                continue

            executed_tools.add(tool_key)

            result = await self.use_tool(
                tool_name,
                _autonomous=True,
                **arguments
            )

            results.append({
                "tool": tool_name,
                "result": str(result)
            })

        return results

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

        # Run autonomous tasks when enabled.
        autonomous_results = await self.run_autonomous_task(question)

        # Use conversational tool selection only when autonomous
        # execution has not already handled the request.
        tool_results = []

        if not autonomous_results:
            actions = await self.tool_selector.select_tools(question)

            for action in actions:

                tool_name = action.get("tool")
                arguments = action.get("arguments", {})

                # Validate the selected tool again before execution.
                if tool_name not in get_available_tools():
                    continue

                if not isinstance(arguments, dict):
                    continue

                try:
                    result = await self.use_tool(
                        tool_name,
                        **arguments
                    )
                except Exception as exc:
                    result = f"Tool execution failed: {exc}"

                tool_results.append({
                    "tool": tool_name,
                    "result": result
                })

                # Format verified MT5 results.
        if tool_results and any(
            item["tool"].startswith("mt5_")
            for item in tool_results
        ):
            formatted_results = []

            for item in tool_results:
                tool_name = item["tool"]
                result = item["result"]

                if (
                    tool_name == "mt5_get_account"
                    and isinstance(result, dict)
                    and result.get("status") == "SUCCESS"
                ):
                    data = result.get("data", {})

                    balance = data.get("balance", "N/A")
                    equity = data.get("equity", "N/A")

                    if isinstance(balance, (int, float)):
                        balance = f"{balance:,.2f}"

                    if isinstance(equity, (int, float)):
                        equity = f"{equity:,.2f}"

                    formatted_results.append(
                        "NEXUS AI Ã¢â‚¬â€ MT5 ACCOUNT\n"
                        "------------------------------\n"
                        f"Server: {data.get('server', 'N/A')}\n"
                        f"Balance: {balance} {data.get('currency', '')}\n"
                        f"Equity: {equity} {data.get('currency', '')}\n"
                        f"Currency: {data.get('currency', 'N/A')}\n"
                        "Status: CONNECTED\n"
                        "Execution: READ ONLY"
                    )
                else:
                    formatted_results.append(
                        f"{tool_name}:\n"
                        f"{json.dumps(result, indent=2, default=str) if isinstance(result, (dict, list)) else result}"
                    )

            answer = "\n\n".join(formatted_results)

            save_message("assistant", answer)

            return answer

        history = get_recent_messages(limit=20)

        messages = [
            {
                "role": "system",
                "content": self.build_system_context()
            }
        ] + history

        if autonomous_results:
            messages.append({
                "role": "system",
                "content": (
                    "AUTONOMOUS EXECUTION RESULTS:\n"
                    f"{autonomous_results}\n"
                    "Explain these actual results to the user. "
                    "Do not claim anything else was executed."
                )
            })

        if tool_results:
            messages.append({
                "role": "system",
                "content": (
                    "CONVERSATIONAL TOOL EXECUTION RESULTS:\n"
                    f"{json.dumps(tool_results, indent=2)}\n"
                    "Explain these actual results accurately. "
                    "Never invent tool results or claim an action "
                    "succeeded if it failed or was cancelled."
                )
            })

        answer = await self.ai.generate(messages)

        save_message("assistant", answer)

        return answer

    async def run_mining_cycle(self, opportunities=None, electricity_price_per_kwh=None, hardware=None):
        """Central Brain interface for policy-controlled mining decisions."""
        from integrations.xmrig import autopilot

        if opportunities is None or hardware is None or electricity_price_per_kwh is None:
            return {
                "status": "INPUT_REQUIRED",
                "required": ["market opportunities", "electricity price", "hardware telemetry"]
            }

        return autopilot.run_cycle(
            opportunities=opportunities,
            electricity_price_per_kwh=electricity_price_per_kwh,
            hardware=hardware
        )

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

    async def use_tool(self, tool_name, _autonomous=False, **kwargs):

        # MCP tools enforce their own approval inside tools.manager.
        if tool_name.startswith("mcp_"):
            return await execute_tool(tool_name, **kwargs)

        if tool_name == "youtube_upload_autonomous":
            if not _autonomous:
                return "Autonomous upload tool is restricted to the autonomous task runner."
            return await execute_tool(tool_name, **kwargs)

        if tool_name == "youtube_upload":
            return await execute_tool(tool_name, **kwargs)

        # X publishing tools enforce approval internally.
        # X Growth publication delegates to those same protected wrappers.

        if tool_name in ("x_post", "x_thread", "x_growth_publish_draft"):

            return await execute_tool(tool_name, **kwargs)


        approved = approve_tool_call(tool_name, kwargs)

        if not approved:
            return "Action cancelled. Permission denied."

        return await execute_tool(tool_name, **kwargs)






from core.settings import load_settings
