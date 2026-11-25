"""NEXUS AI premium terminal interface."""
import os
import sys
import time
import shutil

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich import box
    RICH = True
    console = Console()
except ImportError:
    RICH = False
    console = None

RESET = "\033[0m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"

def _color(text, color):
    if not sys.stdout.isatty():
        return str(text)
    return color + str(text) + RESET

def clear():
    if sys.stdout.isatty():
        os.system("cls" if os.name == "nt" else "clear")

def banner(version="0.2.0"):
    width = min(shutil.get_terminal_size((100, 25)).columns, 110)
    if RICH:
        title = Text()
        title.append("NEXUS", style="bold bright_cyan")
        title.append(" AI", style="bold bright_magenta")
        title.append("\nAUTONOMOUS INTELLIGENCE PLATFORM", style="bright_white")
        title.append(f"\nVersion {version}  |  SYSTEM ONLINE", style="dim cyan")
        console.print(Panel(title, border_style="bright_cyan",
                            box=box.DOUBLE, padding=(1, 4)))
    else:
        print(_color("?" + "?" * (width-2) + "?", CYAN))
        print(_color("?" + " N E X U S   A I ".center(width-2) + "?", MAGENTA + BOLD))
        print(_color("?" + "AUTONOMOUS INTELLIGENCE PLATFORM".center(width-2) + "?", CYAN))
        print(_color("?" + f"VERSION {version}  |  SYSTEM ONLINE".center(width-2) + "?", GREEN))
        print(_color("?" + "?" * (width-2) + "?", CYAN))

def section(title):
    if RICH:
        console.rule(f"[bold bright_cyan]{title}[/]")
    else:
        print("\n" + _color("? " + title.upper() + " " + "?" * 35, CYAN + BOLD))

def status(label, value, state="info"):
    colors = {"success": GREEN, "warning": YELLOW, "error": RED, "info": CYAN}
    if RICH:
        styles = {"success": "bold green", "warning": "bold yellow",
                  "error": "bold red", "info": "bold cyan"}
        console.print(f"[{styles.get(state, 'cyan')}]?[/] {label}: {value}")
    else:
        print(f"{_color('?', colors.get(state, CYAN))} {label}: {value}")

def menu(items, title="COMMAND CENTER"):
    section(title)
    if RICH:
        table = Table(box=box.ROUNDED, border_style="bright_blue")
        table.add_column("#", style="bold bright_magenta", justify="right")
        table.add_column("OPERATION", style="bold bright_cyan")
        for index, item in enumerate(items, 1):
            table.add_row(str(index).zfill(2), str(item))
        console.print(table)
    else:
        for index, item in enumerate(items, 1):
            print(_color(f"  {index:02d}  ? ", MAGENTA + BOLD) + str(item))

def dashboard(data):
    section("SYSTEM INTELLIGENCE")
    for key, value in data.items():
        status(key, value)

def success(message):
    status("SUCCESS", message, "success")

def warning(message):
    status("NOTICE", message, "warning")

def error(message):
    status("ERROR", message, "error")

def progress(message, duration=0.8):
    if RICH:
        with console.status(f"[bright_cyan]{message}...[/]", spinner="dots"):
            time.sleep(max(0, duration))
    else:
        print(_color("? " + message, CYAN))
        if sys.stdout.isatty():
            for _ in range(3):
                print(_color("?", MAGENTA), end="", flush=True)
                time.sleep(max(0, duration)/3)
            print()

def prompt(message="Select an operation"):
    if RICH:
        return console.input(f"[bold bright_magenta]?[/] [bright_white]{message}: [/]")
    return input(_color("? " + message + ": ", MAGENTA + BOLD))
