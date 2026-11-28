import json
from core.settings import load_settings
from brain.ollama_client import OllamaClient
from memory.store import save_message, get_recent_messages
from tools.manager import execute_tool, get_available_tools, get_mcp_servers
from tools.approval import approve_tool_call
from tools.github_tools import READ_ONLY_TOOLS
from skills.manager import list_skills, read_skill
from agents.dispatcher import dispatch_request
from core.toolcalling.selector import ToolSelector
from integrations.dspy import DSPyEngine
from integrations.evolution import EvolutionEngine
from integrations.autonomy import AutonomousCoordinator
from integrations.youtube.upload import load_config

# Read-only operations and bounded local processing only.
# Publishing, trading, deletion, account changes and control operations are excluded.
AUTONOMOUS_SAFE_TOOLS = frozenset({
    "list_files", "read_file",
    "web_research", "trend_discovery",
    "signal_commander_discover", "signal_commander_dashboard",
    "signal_commander_memory", "signal_commander_insights",
    "signal_commander_report_search", "signal_commander_registry_audit",
    "xmrig_status", "xmrig_health", "xmrig_logs", "xmrig_recovery_check",
    "video_probe", "video_transcribe", "video_detect_highlights",
    "video_extract_clip", "video_create_vertical_short",
    "video_create_subtitles", "video_burn_subtitles",
    "youtube_status", "youtube_channel",
    "x_status", "x_account", "x_analytics",
    "x_search_trends", "x_account_timeline",
    "mt5_get_account", "mt5_get_price", "mt5_get_positions",
    "mt5_get_history", "mt5_get_strategy_signal",
})
class NexusAgent:

    STANDARD_USER_TOOLS = frozenset({
        "web_research",
        "trend_discovery",
    })

    def __init__(self, user_id=None, user_role=None):
        self.user_id = str(user_id) if user_id is not None else None
        self.user_role = user_role
        self.ai = OllamaClient()
        self.tool_selector = ToolSelector(self.ai)
        self.intelligence = DSPyEngine()
        self.evolution = EvolutionEngine()
        self.autonomy = AutonomousCoordinator(self)



    async def run_autonomous_cycle(self, task, executor=None):
        return await self.autonomy.run_cycle(task, executor=executor)

    async def autonomous_evaluate_candidate(self, candidate_id, baseline, candidate, metric):
        return await self.autonomy.evaluate_candidate(
            candidate_id, baseline, candidate, metric
        )

    async def autonomous_optimize_candidate(self, program, metric, candidate_id):
        return await self.autonomy.optimize_candidate(
            program, metric, candidate_id
        )

    def add_learning_evaluation_case(self, inputs, expected, approved=False, provenance=None):
        return self.evolution.add_evaluation_case(inputs, expected, approved, provenance)

    def evaluate_learning_candidate(self, candidate_id, baseline_predictor,
                                    candidate_predictor, metric,
                                    minimum_score=None, maximum_regression=None):
        return self.evolution.evaluate_candidate(
            candidate_id, baseline_predictor, candidate_predictor, metric,
            minimum_score, maximum_regression
        )

    def optimize_learning_candidate(self, program, metric, candidate_id, max_demos=None):
        return self.evolution.optimize_candidate(
            program, metric, candidate_id, max_demos=max_demos
        )

    def record_learning_experience(self, task, outcome, approved=False, provenance=None):
        """Record a redacted raw experience; approval is required before curation."""
        return self.evolution.record_approved_experience(
            task, outcome, approved=approved, provenance=provenance
        )

    def curate_learning_experience(self, record, approved=False):
        """Add an approved experience to the curated learning dataset."""
        return self.evolution.curate_experience(record, approved=approved)

    def run_dspy_improvement_cycle(
        self, program, metric, max_candidates=1, max_seconds=120,
        max_demos=None
    ):
        """Explicitly run bounded DSPy optimization and evaluation."""
        if getattr(self.autonomy, "_running", False):
            raise RuntimeError(
                "Cannot optimize while an autonomous task cycle is running."
            )

        return self.evolution.run_improvement_cycle(
            program=program,
            metric=metric,
            max_candidates=max_candidates,
            max_seconds=max_seconds,
            max_demos=max_demos,
            stop_check=self.autonomy._check_stop,
        )

    def curate_latest_verified_experience(self, cycle_id):
        return self.evolution.curate_latest_verified_experience(cycle_id)

    def register_model_candidate(self, candidate_id, metadata):
        """Register a candidate version without changing the active model."""
        return self.evolution.register_candidate(candidate_id, metadata)

    def promote_model_candidate(self, candidate_id, human_approval=False, evaluation_passed=False):
        """Promotion remains blocked by registry policy unless explicitly enabled."""
        return self.evolution.promote_candidate(
            candidate_id,
            human_approval=human_approval,
            evaluation_passed=evaluation_passed,
        )

    def rollback_model_candidate(self, human_approval=False):
        return self.evolution.rollback(human_approval=human_approval)

    async def dspy_reason(self, question, context=""):
        """Optional DSPy reasoning; never executes tools."""
        try:
            return await self.intelligence.areason(question, context)
        except Exception:
            return None

    async def dspy_plan(self, question):
        """Generate a proposal, validating tools without executing them."""
        try:
            available = get_available_tools()
            result = await self.intelligence.aplan(question, available)

            import json
            proposed = json.loads(result["actions_json"])

            if not isinstance(proposed, dict):
                return None

            actions = proposed.get("actions", [])

            if not isinstance(actions, list):
                return None

            validated = []
            rejected = 0

            # Autonomous DSPy plans may contain only explicitly allowlisted
            # routine tools. Protected actions remain outside this pathway.
            for action in actions[:3]:
                if not isinstance(action, dict):
                    rejected += 1
                    continue

                tool = action.get("tool")
                arguments = action.get("arguments", {})

                if (
                    isinstance(tool, str)
                    and tool in available
                    and tool in AUTONOMOUS_SAFE_TOOLS
                    and self._tool_allowed(tool)
                    and isinstance(arguments, dict)
                ):
                    validated.append({
                        "tool": tool,
                        "arguments": arguments
                    })
                else:
                    rejected += 1

            return {
                "reasoning": result.get("reasoning", ""),
                "actions": validated,
                "rejected_proposals": rejected,
                "requires_approval": False,
                "execution_mode": "permission_controlled_autonomy",
                "executed": False
            }

        except Exception:
            return None

    async def dspy_evaluate(self, task, expected, actual):
        """Evaluate an outcome without changing production behavior."""
        try:
            result = await self.intelligence.aevaluate(
                task, expected, actual
            )

            score = float(result["score"])

            if not 0.0 <= score <= 1.0:
                return None

            return {
                "score": score,
                "feedback": result["feedback"],
                "promotion_allowed": False
            }

        except Exception:
            return None

    def _tool_allowed(self, tool_name):
        if self.user_role == "user":
            return tool_name in self.STANDARD_USER_TOOLS
        if self.user_role not in (None, "admin"):
            return False
        return True
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

        if self.user_role == "user":
            safe_tools = sorted(self.STANDARD_USER_TOOLS)
        else:
            youtube_config = load_config()
            if youtube_config.get("allow_autonomous_private_uploads", False):
                safe_tools.append("youtube_upload_autonomous")

            available_tools = set(get_available_tools())
            safe_tools += [
                f"github_{tool}"
                for tool in sorted(READ_ONLY_TOOLS)
                if f"github_{tool}" in available_tools
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

        save_message("user", question, user_id=self.user_id)

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
                if (
                    tool_name not in get_available_tools()
                    or not self._tool_allowed(tool_name)
                ):
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

            save_message("assistant", answer, user_id=self.user_id)

            return answer

        history = get_recent_messages(
            limit=20,
            user_id=self.user_id,
            is_admin=(self.user_role == "admin")
        )

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

        save_message("assistant", answer, user_id=self.user_id)

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

        save_message("user", question, user_id=self.user_id)

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

        save_message("assistant", answer, user_id=self.user_id)

        return answer
    def available_tools(self):
        return get_available_tools()

    def available_skills(self):
        return list_skills()

    def load_skill(self, skill_name):
        return read_skill(skill_name)

    async def use_tool(self, tool_name, _autonomous=False, **kwargs):

        # Check role permissions before every special execution path.
        if not self._tool_allowed(tool_name):
            return "Action denied. This tool is not available to your account role."

        # GitHub and MCP executors enforce approval inside tools.manager.
        if tool_name.startswith("github_"):
            return await execute_tool(tool_name, **kwargs)

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


        approved = False

        # Policy-authorized autonomy applies ONLY to the existing
        # explicitly allowlisted safe tools. Role checks above remain.
        if _autonomous and tool_name in AUTONOMOUS_SAFE_TOOLS:
            import json
            from pathlib import Path

            policy_path = Path(__file__).resolve().parents[1] / "config" / "autonomy_policy.json"
            try:
                policy = json.loads(policy_path.read_text(encoding="utf-8"))
                autonomy = policy.get("autonomy", {})
                safety = policy.get("safety", {})
                approved = bool(
                    autonomy.get("autonomous_task_execution", False)
                    and safety.get("require_existing_tool_permissions", True)
                    and not safety.get("automatic_dangerous_tool_execution", True)
                    and self._tool_allowed(tool_name)
                )
            except Exception:
                approved = False

        # Preserve the existing approval manager for everything else.
        if not approved:
            approved = approve_tool_call(tool_name, kwargs)

        if not approved:
            return "Action cancelled. Permission denied."

        return await execute_tool(tool_name, **kwargs)






from core.settings import load_settings
