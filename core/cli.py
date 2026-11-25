import json
import asyncio
import os
import sys
import platform
import sqlite3
import shutil
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich import box
from colorama import just_fix_windows_console
just_fix_windows_console()
from core.agent import NexusAgent
from memory.store import get_recent_messages, DB_PATH
from core.settings import load_settings, save_settings
from core.scheduler import start_scheduler, stop_scheduler, add_reminder, list_reminders, cancel_reminder
from integrations.mt5 import session_controller as mt5_session


# NEXUS AI TERMINAL THEME
class UI:

    console = Console()

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
    @staticmethod
    def success(message):
        UI.console.print(Panel(
            Text(str(message), style="bold bright_green"),
            title="[bold bright_green]? SUCCESS[/]",
            border_style="bright_green", box=box.ROUNDED, padding=(0, 1)
        ))

    @staticmethod
    @staticmethod
    def error(message):
        UI.console.print(Panel(
            Text(str(message), style="bright_white"),
            title="[bold bright_red]? SYSTEM NOTICE[/]",
            border_style="bright_red", box=box.ROUNDED, padding=(0, 1)
        ))

    @staticmethod
    @staticmethod
    def info(message):
        UI.console.print(Text.assemble(
            ("? ", "bold bright_cyan"), (str(message), "bright_white")
        ))

    @staticmethod
    @staticmethod
    def banner():
        UI.clear()
        width = min(max(shutil.get_terminal_size((100, 30)).columns - 2, 64), 112)
        logo = Text()
        logo.append("N E X U S", style="bold bright_cyan")
        logo.append("  A I", style="bold bright_magenta")

        hero = Table.grid(expand=True)
        hero.add_column(justify="center")
        hero.add_row(logo)
        hero.add_row(Text("????????????????????????????????????????????????????", style="bright_blue"))
        hero.add_row(Text("INTELLIGENCE  /  AUTOMATION  /  CREATION", style="bold bright_white"))
        hero.add_row(Text("Think deeper. Move faster. Build without limits.", style="italic bright_magenta"))
        hero.add_row(Text(""))
        hero.add_row(Text(datetime.now().strftime("%A  |  %d %B %Y  |  %H:%M:%S"), style="dim bright_cyan"))

        UI.console.print()
        UI.console.print(Panel(
            Align.center(hero, vertical="middle"),
            width=width,
            box=box.DOUBLE,
            border_style="bright_magenta",
            padding=(2, 3),
            title="[bold bright_cyan]? NEXUS AI // CORE SYSTEM ?[/]",
            subtitle="[bold bright_magenta] SECURE ? MODULAR ? INTELLIGENT [/]"
        ))

        quick = Table.grid(expand=True, padding=(0, 2))
        for _ in range(4):
            quick.add_column(justify="center")
        quick.add_row(
            "[bold bright_cyan]/agents[/]\n[dim]Specialists[/]",
            "[bold bright_magenta]/skills[/]\n[dim]Capabilities[/]",
            "[bold bright_green]/status[/]\n[dim]System health[/]",
            "[bold bright_yellow]/help[/]\n[dim]Commands[/]"
        )
        UI.console.print(Panel(quick, border_style="bright_blue", box=box.ROUNDED))
        UI.console.print()



    @staticmethod
    @staticmethod
    def status():
        settings = load_settings()
        try:
            import psutil
            cpu = f"{psutil.cpu_percent(interval=None):.0f}%"
            memory = psutil.virtual_memory()
            ram = f"{memory.percent:.0f}% used | {memory.available / (1024**3):.1f} GB free"
        except Exception:
            cpu, ram = "Unavailable", "Unavailable"

        autonomous = bool(settings.get("autonomous_mode"))
        approval = bool(settings.get("require_approval", True))
        table = Table(
            title="[bold bright_white]? LIVE SYSTEM OVERVIEW ?[/]",
            caption="[dim]NEXUS AI ? LOCAL COMMAND CENTRE[/]",
            box=box.ROUNDED,
            border_style="bright_blue",
            header_style="bold bright_magenta",
            title_style="bold bright_cyan",
            expand=True,
            padding=(0, 1)
        )
        table.add_column("SYSTEM COMPONENT", style="bold bright_white")
        table.add_column("LIVE STATE", style="bright_cyan")
        table.add_column("INDICATOR", justify="right")

        table.add_row("AI PROVIDER", str(settings.get("ai_provider") or "Not configured").upper(), "[green]? CONFIGURED[/]")
        table.add_row("AI MODEL", str(settings.get("model") or "Not configured"), "[cyan]? SELECTED[/]")
        table.add_row("AUTONOMOUS MODE", "ENABLED" if autonomous else "DISABLED",
                      "[green]? ACTIVE[/]" if autonomous else "[yellow]? STANDBY[/]")
        table.add_row("ACTION APPROVAL", "REQUIRED" if approval else "NOT REQUIRED",
                      "[green]? PROTECTED[/]" if approval else "[red]? REVIEW[/]")
        table.add_row("SPECIALIST AGENTS", str(len(settings.get("agents", []))), "[bright_magenta]? REGISTERED[/]")
        table.add_row("ENABLED SKILLS", str(len(settings.get("enabled_skills", []))), "[bright_magenta]? AVAILABLE[/]")
        table.add_row("CPU UTILIZATION", cpu, "[cyan]? TELEMETRY[/]")
        table.add_row("MEMORY", ram, "[cyan]? TELEMETRY[/]")
        table.add_row("OPERATING SYSTEM", f"{platform.system()} {platform.release()}", "[green]? DETECTED[/]")

        UI.console.print(table)
        UI.console.print(Align.center(Text(
            "ALL SYSTEM ACTIONS REMAIN SUBJECT TO CONFIGURED SAFETY CONTROLS",
            style="dim bright_cyan"
        )))
        UI.console.print()


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
    @staticmethod
    def help():
        groups = {
            "01  BRAIN & INTELLIGENCE": [
                ("/agents", "Explore specialist agents"),
                ("/skills", "Browse NEXUS capabilities"),
                ("/tools", "Inspect registered tools"),
                ("/use <skill> <request>", "Activate a specialist"),
                ("/research <url>", "Research a webpage"),
                ("/history", "Conversation history"),
                ("/memory", "Persistent memory"),
            ],
            "02  X GROWTH & CONTENT": [
                ("/x-growth", "Discover opportunities and create drafts"),
                ("/x-drafts", "Browse saved drafts"),
                ("/x-preview <id>", "Preview a draft"),
                ("/x-publish <id>", "Request human publication approval"),
                ("/x-analytics", "Review publication analytics"),
            ],
            "03  AUTOMATION": [
                ("/schedule add 10m <message>", "Create a reminder"),
                ("/schedule list", "View reminders"),
                ("/schedule cancel <id>", "Cancel a reminder"),
            ],
            "04  MT5 BRIDGE": [
                ("/mt5-server-status", "Inspect bridge status"),
                ("/mt5-server-start", "Start or reuse the bridge"),
                ("/mt5-server-restart", "Restart the bridge"),
                ("/mt5-server-stop", "Stop the bridge"),
            ],
            "05  MT5 DEMO TRADING": [
                ("/trading-plan", "View demo trading plan"),
                ("/trading-go", "Approve and start a demo session"),
                ("/trading-status", "Inspect trading session"),
                ("/trading-stop", "Stop trading"),
                ("/trading-emergency-stop", "Emergency stop"),
                ("/trading-emergency-clear", "Request emergency-stop clearance"),
            ],
            "06  SYSTEM": [
                ("/status", "Live system dashboard"),
                ("/config", "System configuration"),
                ("/settings", "Settings and safeguards"),
                ("/autonomous", "View autonomous mode"),
                ("/autonomous on/off", "Change autonomous mode"),
                ("/diagnostics", "System health checks"),
                ("/backup", "Back up memory database"),
                ("/export", "Export conversations and research"),
            ],
            "07  TERMINAL": [
                ("/help", "Command directory"),
                ("/clear", "Clear terminal"),
                ("/exit", "Close NEXUS AI"),
            ],
        }
        UI.console.print()
        UI.console.print(Panel(
            Align.center(Text.assemble(
                ("N E X U S", "bold bright_cyan"),
                ("  A I", "bold bright_magenta"),
                ("\nCOMMAND CENTRE", "bold bright_white"),
                ("\nExplore  ?  Orchestrate  ?  Execute safely", "italic bright_cyan")
            )),
            border_style="bright_magenta", box=box.DOUBLE, padding=(1, 2)
        ))
        for i, (title, commands) in enumerate(groups.items()):
            table = Table(
                box=box.SIMPLE_HEAVY, expand=True,
                header_style="bold bright_white", padding=(0, 1)
            )
            table.add_column("COMMAND", style="bold bright_cyan", no_wrap=True)
            table.add_column("CAPABILITY", style="white")
            for command, description in commands:
                table.add_row(command, description)
            UI.console.print(Panel(
                table, title=f"[bold bright_magenta]{title}[/]",
                border_style="bright_blue" if i % 2 == 0 else "bright_magenta",
                box=box.ROUNDED, padding=(0, 1)
            ))
        UI.console.print(Align.center(
            Text("? NEXUS AI  ?  INTELLIGENCE AT YOUR COMMAND ?",
                 style="bold bright_cyan")
        ))
        UI.console.print()


async def chat():

    agent = NexusAgent()
    start_scheduler()

    UI.banner()
    UI.status()

    UI.console.print(Panel(
        Align.center(Text.assemble(
            ("? ", "bold bright_green"),
            ("NEXUS CORE ONLINE", "bold bright_white"),
            ("\\nType ", "dim"),
            ("/help", "bold bright_cyan"),
            (" to explore your command centre.", "dim")
        )),
        border_style="bright_green",
        box=box.ROUNDED,
        padding=(0, 2)
    ))

    while True:

        try:
            prompt = "[bold bright_magenta]? NEXUS[/] [bold bright_cyan]?[/] "

            question = (await asyncio.to_thread(
                UI.console.input, prompt
            )).strip()

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

            if command == "/mt5-server-status":
                mt5_session.bridge_server_status()
                continue

            elif command == "/mt5-server-start":
                try:
                    mt5_session.start_bridge_server()
                except Exception as error:
                    UI.error(f"MT5 API start failed: {error}")
                continue

            elif command == "/mt5-server-restart":
                try:
                    mt5_session.restart_bridge_server()
                except Exception as error:
                    UI.error(f"MT5 API restart failed: {error}")
                continue

            elif command == "/mt5-server-stop":
                try:
                    mt5_session.stop_bridge_server()
                except Exception as error:
                    UI.error(f"MT5 API stop failed: {error}")
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

            elif command == "/trading-emergency-stop":
                mt5_session.emergency_stop()
                continue

            elif command == "/trading-emergency-clear":
                try:
                    mt5_session.clear_emergency_stop()
                except Exception as error:
                    UI.error(f"Emergency stop clearance blocked: {error}")
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

            # SIGNAL COMMANDER PATCH
            elif command == "/signal":
                UI.console.print(Panel(
                    "Signal Commander commands\\n"
                    "/signal-dashboard  Dashboard\\n"
                    "/signal-insights   Insights\\n"
                    "/signal-memory     Memory\\n"
                    "/signal-search <query>  Search reports\\n"
                    "/signal-audit      Registry audit",
                    title="[bold bright_cyan]SIGNAL COMMANDER[/]",
                    border_style="bright_cyan"
                ))
                continue

            elif command.startswith((
                "/signal-dashboard", "/signal-insights",
                "/signal-memory", "/signal-search", "/signal-audit"
            )):
                parts = question.split(maxsplit=1)
                cmd = parts[0].lower()
                names = {
                    "/signal-dashboard": "signal_commander_dashboard",
                    "/signal-insights": "signal_commander_insights",
                    "/signal-memory": "signal_commander_memory",
                    "/signal-search": "signal_commander_report_search",
                    "/signal-audit": "signal_commander_registry_audit",
                }
                tool = names[cmd]

                if cmd == "/signal-search" and len(parts) != 2:
                    UI.error("Usage: /signal-search <query>")
                    continue

                if tool not in set(agent.available_tools()):
                    UI.error("Signal Commander tool is not registered: " + tool)
                    continue

                try:
                    if cmd == "/signal-search":
                        result = await agent.use_tool(
                            tool, query=parts[1].strip()
                        )
                    else:
                        result = await agent.use_tool(tool)

                    UI.console.print(Panel(
                        str(result),
                        title="[bold bright_cyan]SIGNAL COMMANDER / "
                              + cmd[1:].upper() + "[/]",
                        border_style="bright_cyan"
                    ))
                except Exception as error:
                    UI.error("Signal Commander request failed: " + str(error))
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
                tools = sorted(agent.available_tools())
                table = Table(title=f"REGISTERED TOOLS  ?  {len(tools)}", box=box.ROUNDED, border_style="bright_cyan", expand=True)
                table.add_column("#", style="dim", width=5)
                table.add_column("TOOL", style="bold bright_cyan")
                table.add_column("STATUS", justify="right")
                for index, tool in enumerate(tools, 1):
                    table.add_row(str(index), str(tool), "[green]REGISTERED[/]")
                UI.console.print(table)
                continue

            elif command == "/skills":
                skills = sorted(agent.available_skills())
                table = Table(title=f"NEXUS CAPABILITY LIBRARY  ?  {len(skills)} SKILLS", box=box.ROUNDED, border_style="bright_magenta", expand=True)
                table.add_column("#", style="dim", width=5)
                table.add_column("SKILL", style="bold bright_white")
                table.add_column("AVAILABILITY", style="green", justify="right")
                for index, skill in enumerate(skills, 1):
                    table.add_row(str(index), str(skill), "READY")
                UI.console.print(table)
                continue

            elif command == "/agents":
                from agents.manager import list_agents

                agents = list_agents()
                UI.console.print(Panel(
                    Align.center(Text(f"SPECIALIST AGENT NETWORK  ?  {len(agents)} AGENTS", style="bold bright_white")),
                    border_style="bright_magenta",
                    box=box.DOUBLE
                ))
                for agent_id, details in agents.items():
                    skills = details.get("skills", [])
                    card = Table.grid(padding=(0, 1))
                    card.add_column(style="bold bright_cyan")
                    card.add_column(style="white")
                    card.add_row("AGENT", str(details.get("name", agent_id)))
                    card.add_row("IDENTIFIER", str(agent_id))
                    card.add_row("CAPABILITIES", ", ".join(map(str, skills)) or "No skills listed")
                    UI.console.print(Panel(card, border_style="bright_cyan", box=box.ROUNDED))
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

                with UI.console.status(
                    f"[bold bright_magenta]Connecting to {skill_name} specialist...",
                    spinner="dots"
                ):
                    answer = await agent.ask_specialist(
                        skill_name,
                        specialist_question
                    )

                UI.console.print(Panel(
                    str(answer),
                    title=f"[bold bright_magenta] {skill_name.upper()} SPECIALIST [/]",
                    subtitle="[italic bright_cyan] NEXUS SPECIALIST NETWORK [/]",
                    border_style="bright_magenta",
                    box=box.ROUNDED,
                    padding=(1, 2)
                ))
                continue

            elif command == "/history":
                history = get_recent_messages(10)

                UI.console.print(Panel(
                    Align.center(Text(
                        f"CONVERSATION TIMELINE  ?  {len(history)} MESSAGES",
                        style="bold bright_white"
                    )),
                    border_style="bright_cyan",
                    box=box.DOUBLE
                ))

                for index, message in enumerate(history, 1):
                    role = str(message.get("role", "unknown")).upper()
                    content = str(message.get("content", ""))
                    is_user = role == "USER"
                    UI.console.print(Panel(
                        content,
                        title=f"[bold {'bright_green' if is_user else 'bright_cyan'}] {index:02d}  ?  {role} [/]",
                        border_style="bright_green" if is_user else "bright_cyan",
                        box=box.ROUNDED,
                        padding=(1, 2)
                    ))
                continue

            # NORMAL AI CHAT

            with UI.console.status(
                "[bold bright_cyan]NEXUS is thinking...",
                spinner="dots"
            ):
                answer = await agent.ask(question)

            UI.console.print(Panel(
                str(answer),
                title="[bold bright_cyan]? NEXUS INTELLIGENCE RESPONSE ?[/]",
                subtitle="[italic bright_magenta] THINK  ?  REASON  ?  CREATE [/]",
                border_style="bright_cyan",
                box=box.ROUNDED,
                padding=(1, 2)
            ))
            UI.console.print()

        except KeyboardInterrupt:
            UI.console.print(Panel(
                Align.center(Text("SESSION INTERRUPTED  ?  RETURNING SAFELY", style="bold yellow")),
                border_style="yellow",
                box=box.ROUNDED
            ))
            mt5_session.stop_session()
            stop_scheduler()
            break

        except Exception as error:
            UI.console.print(Panel(
                Text(str(error), style="white"),
                title="[bold red] NEXUS SYSTEM ERROR [/]",
                subtitle="[dim] The session remains available unless a safety control stopped it. [/]",
                border_style="red",
                box=box.ROUNDED,
                padding=(1, 2)
            ))


if __name__ == "__main__":
    asyncio.run(chat())
