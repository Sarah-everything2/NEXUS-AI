import json
import asyncio
import os
import sys
import platform
import sqlite3
import shutil
from datetime import datetime
from colorama import just_fix_windows_console
just_fix_windows_console()
from core.agent import NexusAgent
from memory.store import get_recent_messages, DB_PATH
from core.settings import load_settings, save_settings
from core.scheduler import start_scheduler, stop_scheduler, add_reminder, list_reminders, cancel_reminder
from integrations.mt5 import session_controller as mt5_session


# NEXUS AI TERMINAL THEME
class UI:

    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    PURPLE = "\033[95m"

    @staticmethod
    def backup():

        database = os.path.join("memory", "nexus_memory.db")
        backup_folder = "backups"

        if not os.path.exists(database):
            UI.error("Memory database not found.")
            return

        os.makedirs(backup_folder, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(
            backup_folder,
            f"nexus_memory_{timestamp}.db"
        )

        try:
            with sqlite3.connect(database) as source:
                with sqlite3.connect(backup_path) as destination:
                    source.backup(destination)

            UI.success(f"Backup created: {backup_path}")

        except sqlite3.Error as error:
            UI.error(f"Backup failed: {error}")

    @staticmethod
    def clear():
        os.system("cls" if os.name == "nt" else "clear")

    @staticmethod
    def line():
        print(UI.CYAN + "-" * 65 + UI.RESET)

    @staticmethod
    def success(message):
        print(f"{UI.GREEN}[+] {message}{UI.RESET}")

    @staticmethod
    def error(message):
        print(f"{UI.RED}[!] {message}{UI.RESET}")

    @staticmethod
    def info(message):
        print(f"{UI.CYAN}[*] {message}{UI.RESET}")

    @staticmethod
    def banner():

        UI.clear()

        print(UI.CYAN + UI.BOLD)
        print("             NEXUS AI COMMAND CENTRE")
        print(UI.RESET)

        print(UI.PURPLE + UI.BOLD)
        print("              YOUR PERSONAL AI ASSISTANT")
        print(UI.RESET)

        UI.line()

    @staticmethod
    def status():

        settings = load_settings()

        print(f"{UI.WHITE}SYSTEM STATUS{UI.RESET}")

        print(
            f"  Model:       "
            f"{UI.GREEN}{settings['model'] or 'Not configured'}{UI.RESET}"
        )

        print(
            f"  Autonomous:  "
            f"{UI.GREEN if settings['autonomous_mode'] else UI.YELLOW}"
            f"{'ENABLED' if settings['autonomous_mode'] else 'DISABLED'}"
            f"{UI.RESET}"
        )

        print(
            f"  Approval:    "
            f"{UI.YELLOW}"
            f"{'REQUIRED' if settings['require_approval'] else 'NOT REQUIRED'}"
            f"{UI.RESET}"
        )

        print(
            f"  Skills:      "
            f"{UI.CYAN}{len(settings['enabled_skills'])} registered{UI.RESET}"
        )

        UI.line()

    @staticmethod
    def diagnostics(agent):

        print(f"\n{UI.CYAN}{UI.BOLD}NEXUS AI SYSTEM DIAGNOSTICS{UI.RESET}")
        UI.line()

        checks = []

        checks.append(("Python", sys.version.split()[0]))
        checks.append(("Operating System", platform.system()))
        checks.append(("AI Model", load_settings().get("model") or "Not configured"))
        checks.append(("Registered Tools", str(len(agent.available_tools()))))
        checks.append(("Registered Skills", str(len(agent.available_skills()))))

        for name, value in checks:
            print(f"{UI.GREEN}OK{UI.RESET}  {name}: {value}")

        database = os.path.join("memory", "nexus_memory.db")

        try:
            with sqlite3.connect(database) as connection:
                result = connection.execute("PRAGMA integrity_check").fetchone()[0]

            if result == "ok":
                print(f"{UI.GREEN}OK{UI.RESET}  Memory Database: Healthy")
            else:
                print(f"{UI.RED}ERROR{UI.RESET}  Memory Database: {result}")

        except sqlite3.Error as error:
            print(f"{UI.RED}ERROR{UI.RESET}  Memory Database: {error}")

        UI.line()
        print(f"{UI.GREEN}Diagnostics completed.{UI.RESET}\n")

    @staticmethod
    def memory():

        print(f"\n{UI.CYAN}{UI.BOLD}NEXUS AI MEMORY MANAGER{UI.RESET}")
        UI.line()

        try:
            with sqlite3.connect(DB_PATH) as connection:

                conversations = connection.execute(
                    "SELECT COUNT(*) FROM conversations"
                ).fetchone()[0]

                research = connection.execute(
                    "SELECT COUNT(*) FROM research_results"
                ).fetchone()[0]

            print(f"{UI.GREEN}Conversation records:{UI.RESET} {conversations}")
            print(f"{UI.GREEN}Research records:{UI.RESET} {research}")

            print(f"\n{UI.YELLOW}RECENT CONVERSATIONS{UI.RESET}")

            history = get_recent_messages(5)

            if not history:
                print("No conversations saved yet.")

            for message in history:
                role = message["role"].upper()
                content = message["content"].replace("\n", " ")
                print(f"{UI.CYAN}{role}:{UI.RESET} {content[:120]}")

            print(f"\n{UI.GREEN}Memory database: HEALTHY{UI.RESET}")

        except sqlite3.Error as error:
            UI.error(f"Memory error: {error}")

        UI.line()

    @staticmethod
    def export():

        export_folder = "exports"
        os.makedirs(export_folder, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = os.path.join(
            export_folder,
            f"nexus_export_{timestamp}.json"
        )

        try:
            with sqlite3.connect(DB_PATH) as connection:
                connection.row_factory = sqlite3.Row

                conversations = [
                    dict(row) for row in connection.execute(
                        "SELECT * FROM conversations ORDER BY id"
                    ).fetchall()
                ]

                research = [
                    dict(row) for row in connection.execute(
                        "SELECT * FROM research_results ORDER BY id"
                    ).fetchall()
                ]

            data = {
                "exported_at": datetime.now().isoformat(),
                "conversations": conversations,
                "research_results": research
            }

            with open(export_path, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=2, ensure_ascii=False)

            UI.success(f"Export completed: {export_path}")
            UI.info(f"Conversations: {len(conversations)}")
            UI.info(f"Research records: {len(research)}")

        except (sqlite3.Error, OSError, TypeError) as error:
            UI.error(f"Export failed: {error}")

    @staticmethod
    def settings():

        config = load_settings()

        print(f"\n{UI.CYAN}{UI.BOLD}NEXUS AI SETTINGS MANAGER{UI.RESET}")
        UI.line()

        items = [
            ("AI Provider", config.get("ai_provider")),
            ("AI Model", config.get("model") or "Not configured"),
            ("Memory", "ENABLED" if config.get("memory_enabled") else "DISABLED"),
            ("Autonomous Mode", "ENABLED" if config.get("autonomous_mode") else "DISABLED"),
            ("Approval Required", "YES" if config.get("require_approval") else "NO"),
            ("File Deletion", "ALLOWED" if config.get("allow_file_deletion") else "BLOCKED"),
            ("Workspace Restriction", "ENABLED" if config.get("workspace_only") else "DISABLED"),
            ("Registered Agents", len(config.get("agents", []))),
            ("Enabled Skills", len(config.get("enabled_skills", []))),
        ]

        for name, value in items:
            print(f"{UI.GREEN}{name:<25}{UI.RESET} {value}")

        print(f"\n{UI.YELLOW}SAFETY PROTECTION{UI.RESET}")

        for name, enabled in config.get("safety", {}).items():
            status = "ON" if enabled else "OFF"
            print(f"  {name}: {status}")

        UI.line()

    @staticmethod
    def autonomous(mode=None):

        settings = load_settings()

        if mode is None:
            status = "ENABLED" if settings.get("autonomous_mode") else "DISABLED"
            UI.info(f"Autonomous Mode: {status}")
            return

        if mode == "on":

            confirmation = input(
                "Type ENABLE to activate autonomous mode: "
            )

            if confirmation != "ENABLE":
                UI.error("Activation cancelled.")
                return

            settings["autonomous_mode"] = True
            settings["require_approval"] = True
            settings["allow_file_deletion"] = False

            save_settings(settings)
            UI.success("Autonomous mode enabled. Safety approvals retained.")

        elif mode == "off":

            settings["autonomous_mode"] = False
            save_settings(settings)
            UI.success("Autonomous mode disabled.")

        else:
            UI.error("Usage: /autonomous [on/off]")

    @staticmethod
    def help():

        print(f"\n{UI.BOLD}{UI.CYAN}NEXUS AI COMMAND CENTRE{UI.RESET}")

        commands = [
            ("/help", "Display commands"),
            ("/skills", "Explore available skills"),
            ("/agents", "View specialist agents"),
            ("/tools", "View registered tools"),
            ("/use <skill> <request>", "Use a specialist agent"),
            ("/research <url>", "Research a webpage"),
            ("/x-growth", "Research opportunities and generate X drafts"),
            ("/x-drafts", "List saved X drafts"),
            ("/x-preview <id>", "Preview an X draft"),
            ("/x-publish <id>", "Request approval to publish an X draft"),
            ("/x-analytics", "View X publication analytics"),
            ("/schedule add 10m <message>", "Create a reminder"),
            ("/schedule list", "View scheduled reminders"),
            ("/schedule cancel <id>", "Cancel a reminder"),
            ("/history", "View conversation history"),
            ("/settings", "Open configuration and safety manager"),
            ("/autonomous", "View autonomous mode status"),
            ("/autonomous on/off", "Enable or disable autonomous mode"),
            ("/trading-plan", "View today's demo trading plan"),
            ("/trading-go", "Approve and start today's demo session"),
            ("/trading-stop", "Request graceful demo session stop"),
            ("/trading-status", "Check demo session processes"),
            ("/config", "View system configuration"),
            ("/status", "View live system status"),
            ("/diagnostics", "Run system health checks"),
            ("/backup", "Create a memory database backup"),
            ("/memory", "Explore conversation and research memory"),
            ("/export", "Export conversations and research to JSON"),
            ("/clear", "Clear terminal"),
            ("/exit", "Close NEXUS AI")
        ]

        for command, description in commands:
            print(
                f"  {UI.GREEN}{command:<38}{UI.RESET}"
                f"{UI.GRAY}{description}{UI.RESET}"
            )

        print()


async def chat():

    agent = NexusAgent()
    start_scheduler()

    UI.banner()
    UI.status()

    print(f"{UI.GREEN}- NEXUS AI CONTROL CENTRE ONLINE{UI.RESET}")
    print(f"{UI.GRAY}Type /help to explore your assistant.{UI.RESET}\n")

    while True:

        try:
            prompt = (
                f"{UI.BOLD}{UI.GREEN}YOU {UI.RESET}"
                f"{UI.CYAN}> {UI.RESET}"
            )

            question = (await asyncio.to_thread(input, prompt)).strip()

            if not question:
                continue

            command = question.lower()

            if command.startswith("/schedule"):

                parts = question.split(maxsplit=4)

                if len(parts) == 1 or parts[1].lower() == "help":
                    print("\nSCHEDULE COMMANDS")
                    print("  /schedule add 10m Take a break")
                    print("  /schedule add 2h Check my project")
                    print("  /schedule repeat 5m hourly Check my system")
                    print("  /schedule repeat 1h daily Review my tasks")
                    print("  /schedule repeat 1d weekly Backup my work")
                    print("  /schedule list")
                    print("  /schedule cancel 1\n")
                    continue

                action = parts[1].lower()

                if action in ("add", "repeat"):

                    try:
                        if action == "add" and len(parts) == 4:
                            duration = parts[2].lower()
                            message = parts[3]
                            repeat = "once"

                        elif action == "repeat" and len(parts) == 5:
                            duration = parts[2].lower()
                            repeat = parts[3].lower()
                            message = parts[4]

                            if repeat not in ("hourly", "daily", "weekly"):
                                raise ValueError(
                                    "Repeat must be hourly, daily, or weekly."
                                )
                        else:
                            raise ValueError("Invalid reminder format. Type /schedule help.")

                        if duration.endswith("m"):
                            minutes = int(duration[:-1])
                        elif duration.endswith("h"):
                            minutes = int(duration[:-1]) * 60
                        elif duration.endswith("d"):
                            minutes = int(duration[:-1]) * 1440
                        else:
                            raise ValueError("Use m, h, or d.")

                        result = add_reminder(minutes, message, repeat)

                        print(f"\n{UI.GREEN}REMINDER SCHEDULED{UI.RESET}")
                        print(f"  ID: {result['id']}")
                        print(f"  Message: {result['message']}")
                        print(f"  Time (UTC): {result['run_at']}")
                        print(f"  Repeat: {result['repeat']}\n")

                    except ValueError as error:
                        UI.error(str(error))

                    continue

                elif action == "list":

                    reminders = list_reminders()

                    print(f"\n{UI.CYAN}{UI.BOLD}SCHEDULED REMINDERS{UI.RESET}")

                    if not reminders:
                        print("  No pending reminders.")
                    else:
                        for reminder in reminders:
                            print(f"\n  ID: {reminder['id']}")
                            print(f"  Message: {reminder['message']}")
                            print(f"  Time (UTC): {reminder['run_at']}")
                            print(f"  Repeat: {reminder['repeat']}")

                    print()
                    continue

                elif action == "cancel" and len(parts) >= 3:

                    try:
                        task_id = int(parts[2])

                        if cancel_reminder(task_id):
                            print(f"\n{UI.GREEN}Reminder cancelled.{UI.RESET}\n")
                        else:
                            UI.error("Pending reminder not found.")

                    except ValueError:
                        UI.error("Enter a valid reminder ID.")

                    continue

                else:
                    UI.error("Invalid schedule command. Type /schedule help.")
                    continue

            if command == "/trading-plan":
                mt5_session.show_plan()
                continue

            elif command == "/trading-go":
                mt5_session.show_plan()
                approval = await asyncio.to_thread(
                    input, "Type GO to approve today's Headway-Demo session: "
                )
                if approval.strip() == "GO":
                    try:
                        mt5_session.start_session(daily_approval=True)
                    except Exception as error:
                        UI.error(f"Trading session not started: {error}")
                else:
                    print("Daily trading approval cancelled.")
                continue

            elif command == "/trading-stop":
                mt5_session.stop_session()
                continue

            elif command == "/trading-status":
                mt5_session.status()
                continue

            if command == "/exit":

                mt5_session.stop_session()
                stop_scheduler()

                print(f"\n{UI.CYAN}NEXUS AI: Shutting down safely.{UI.RESET}")
                break

            elif command == "/export":

                UI.export()
                continue

            elif command == "/memory":

                UI.memory()
                continue

            elif command == "/backup":

                UI.backup()
                continue

            elif command == "/diagnostics":

                UI.diagnostics(agent)
                continue

            elif command == "/help":

                UI.help()
                continue

            elif command == "/clear":

                UI.banner()
                UI.status()
                continue

            elif command.startswith("/autonomous"):

                parts = question.split(maxsplit=1)
                mode = parts[1].lower() if len(parts) > 1 else None

                UI.autonomous(mode)
                continue

            elif command == "/settings":

                UI.settings()
                continue

            elif command in ("/config", "/status"):

                UI.status()
                continue

            elif command == "/x-growth":

                print(f"\n{UI.YELLOW}Researching opportunities and generating X drafts...{UI.RESET}")

                result = await agent.use_tool(
                    "x_growth_run",
                    content_type="post",
                    max_drafts=1,
                    queries_per_category=1,
                )

                print(f"\n{UI.CYAN}{UI.BOLD}X GROWTH RESULTS{UI.RESET}")
                print(result)
                print()
                continue

            elif command == "/x-drafts":

                result = await agent.use_tool("x_growth_list_drafts")

                print(f"\n{UI.CYAN}{UI.BOLD}SAVED X DRAFTS{UI.RESET}")

                for draft in result:
                    print(f"\nID: {draft.get('draft_id')}")
                    print(f"Type: {draft.get('content_type')}")
                    print(f"Status: {draft.get('status')}")
                    print(f"Content: {draft.get('content')}")

                if not result:
                    print("No saved drafts.")

                print()
                continue

            elif command.startswith("/x-preview"):

                parts = question.split(maxsplit=1)

                if len(parts) != 2:
                    UI.error("Usage: /x-preview <draft_id>")
                    continue

                result = await agent.use_tool(
                    "x_growth_preview_draft",
                    draft_id=parts[1].strip(),
                )

                print(f"\n{UI.CYAN}{UI.BOLD}X DRAFT PREVIEW{UI.RESET}")
                print(result)
                print()
                continue

            elif command.startswith("/x-publish"):

                parts = question.split(maxsplit=1)

                if len(parts) != 2:
                    UI.error("Usage: /x-publish <draft_id>")
                    continue

                print(f"\n{UI.YELLOW}Publication requires explicit human approval.{UI.RESET}")

                result = await agent.use_tool(
                    "x_growth_publish_draft",
                    draft_id=parts[1].strip(),
                )

                print(result)
                print()
                continue

            elif command == "/x-analytics":

                result = await agent.use_tool("x_growth_analytics")

                print(f"\n{UI.CYAN}{UI.BOLD}X GROWTH ANALYTICS{UI.RESET}")
                print(result)
                print()
                continue

            elif command == "/tools":

                print(f"\n{UI.CYAN}{UI.BOLD}REGISTERED TOOLS{UI.RESET}")

                for tool in agent.available_tools():
                    print(f"  {UI.GREEN}-{UI.RESET} {tool}")

                print()
                continue

            elif command == "/skills":

                print(f"\n{UI.CYAN}{UI.BOLD}AVAILABLE SKILLS{UI.RESET}")

                for skill in agent.available_skills():
                    print(f"  {UI.GREEN}-{UI.RESET} {skill}")

                print()
                continue

            elif command == "/agents":

                from agents.manager import list_agents

                print(f"\n{UI.CYAN}{UI.BOLD}SPECIALIST AGENTS{UI.RESET}")

                for agent_id, details in list_agents().items():

                    print(f"\n{UI.YELLOW}{details['name']}{UI.RESET}")
                    print(f"  ID: {agent_id}")
                    print(f"  Skills: {', '.join(details['skills'])}")

                print()
                continue

            elif command.startswith("/research"):

                parts = question.split(maxsplit=1)

                if len(parts) < 2:
                    UI.error("Usage: /research https://example.com")
                    continue

                print(f"\n{UI.YELLOW}Researching webpage...{UI.RESET}")

                result = await agent.use_tool(
                    "web_research",
                    url=parts[1].strip()
                )

                print(f"\n{UI.CYAN}{UI.BOLD}RESEARCH RESULTS{UI.RESET}")

                if isinstance(result, dict):

                    print(f"{UI.GREEN}Title:{UI.RESET} {result.get('title', 'Unknown')}")
                    print(f"{UI.GREEN}URL:{UI.RESET} {result.get('url', 'Unknown')}")

                    print(f"\n{UI.BOLD}CONTENT{UI.RESET}")
                    print(result.get("content", "No content"))

                    print(f"\n{UI.GREEN}Status:{UI.RESET} {result.get('status', 'Unknown')}")

                else:
                    print(result)

                print()
                continue

            elif command.startswith("/use "):

                parts = question.split(maxsplit=2)

                if len(parts) < 3:
                    UI.error("Usage: /use <skill> <your request>")
                    continue

                skill_name = parts[1].lower()
                specialist_question = parts[2]

                if skill_name not in agent.available_skills():
                    UI.error("Unknown skill.")
                    continue

                print(f"\n{UI.PURPLE}Connecting to {skill_name} specialist...{UI.RESET}")

                answer = await agent.ask_specialist(
                    skill_name,
                    specialist_question
                )

                print(f"\n{UI.PURPLE}{UI.BOLD}SPECIALIST RESPONSE{UI.RESET}")
                print(answer)
                print()
                continue

            elif command == "/history":

                history = get_recent_messages(10)

                print(f"\n{UI.CYAN}{UI.BOLD}CONVERSATION HISTORY{UI.RESET}")

                for message in history:

                    role = message["role"].upper()

                    print(f"\n{UI.YELLOW}{role}{UI.RESET}")
                    print(message["content"])

                print()
                continue

            # NORMAL AI CHAT

            print(f"\n{UI.GRAY}NEXUS AI is processing your request...{UI.RESET}\n")

            answer = await agent.ask(question)

            print(f"{UI.CYAN}{UI.BOLD}NEXUS AI{UI.RESET}")
            UI.line()
            print(answer)
            UI.line()
            print()

        except KeyboardInterrupt:

            print(f"\n\n{UI.YELLOW}Session interrupted.{UI.RESET}")
            mt5_session.stop_session()
            stop_scheduler()
            break

        except Exception as error:

            UI.error(f"NEXUS AI ERROR: {error}")


if __name__ == "__main__":
    asyncio.run(chat())
