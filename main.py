"""
main.py
-------
CLI entry point for the single-agent chat system.

Usage:
    python main.py

Commands available during the session:
    /reset   – clear conversation history
    /tools   – list available skills
    /quit    – exit (also: /exit, Ctrl-C, Ctrl-D)
"""

import sys

from agent import AIAgent
from skills import TOOL_DEFINITIONS

# ── ANSI colour helpers ────────────────────────────────────────────────
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

BANNER = f"""{CYAN}{BOLD}
╔══════════════════════════════════════════════════════╗
║          Single-Agent AI System  •  Claude           ║
║  Type your message, or a command:                    ║
║    /tools  – list available skills                   ║
║    /reset  – clear conversation history              ║
║    /quit   – exit                                    ║
╚══════════════════════════════════════════════════════╝
{RESET}"""

PROMPT_USER      = f"{GREEN}You   >{RESET} "
PROMPT_ASSISTANT = f"{CYAN}Agent >{RESET} "


def print_tools() -> None:
    """Pretty-print the registered tool names and descriptions."""
    print(f"\n{YELLOW}Available skills:{RESET}")
    for tool in TOOL_DEFINITIONS:
        name = tool["name"]
        desc = tool.get("description", "")
        # Truncate long descriptions for readability
        short = desc[:120] + "…" if len(desc) > 120 else desc
        print(f"  • {BOLD}{name}{RESET}: {short}")
    print()


def main() -> None:
    print(BANNER)

    try:
        agent = AIAgent()
    except EnvironmentError as exc:
        print(f"[Setup error] {exc}")
        sys.exit(1)

    while True:
        try:
            raw = input(PROMPT_USER).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not raw:
            continue

        # ── Built-in commands ──────────────────────────────────────────
        if raw.lower() in ("/quit", "/exit", "quit", "exit"):
            print("Goodbye!")
            break

        if raw.lower() == "/reset":
            agent.reset()
            print(f"{YELLOW}  [Conversation history cleared]{RESET}\n")
            continue

        if raw.lower() == "/tools":
            print_tools()
            continue

        # ── Regular chat turn ──────────────────────────────────────────
        print()  # breathing room before tool output (if any)
        response = agent.chat(raw)
        print(f"{PROMPT_ASSISTANT}{response}\n")


if __name__ == "__main__":
    main()
