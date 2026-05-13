"""
main.py — CLI entry point for the GroqAgent.

Run directly:
    python main.py

Environment:
    GROQ_API_KEY must be set in a .env file (or the shell environment).
"""

import logging
import os
import sys

from dotenv import load_dotenv
from groq import AuthenticationError, RateLimitError, APIConnectionError, APIStatusError

from agent import GroqAgent

# ---------------------------------------------------------------------------
# Logging — single format, written to stdout so Replit's console shows it
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Turn down noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BANNER = """
╔══════════════════════════════════════════════╗
║          GroqAgent — ReAct CLI v1.0          ║
║  Type  'exit' or 'quit'  to stop             ║
║  Type  'reset'           to clear memory     ║
║  Type  'debug'           to toggle debug log ║
╚══════════════════════════════════════════════╝
"""

COMMANDS = {"exit", "quit", "reset", "debug"}


def _toggle_debug() -> None:
    root = logging.getLogger()
    if root.level == logging.DEBUG:
        root.setLevel(logging.INFO)
        print("[system] Debug logging OFF.\n")
    else:
        root.setLevel(logging.DEBUG)
        print("[system] Debug logging ON.\n")


def _load_api_key() -> str:
    """Load GROQ_API_KEY from .env or the environment."""
    load_dotenv()
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        logger.error(
            "GROQ_API_KEY is not set. "
            "Add it to your .env file or set it as an environment variable."
        )
        sys.exit(1)
    return key


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    api_key = _load_api_key()

    try:
        agent = GroqAgent(api_key=api_key)
    except Exception as exc:          # noqa: BLE001
        logger.critical("Failed to initialise GroqAgent: %s", exc)
        sys.exit(1)

    print(BANNER)

    while True:
        # ── Prompt ────────────────────────────────────────────────────
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[system] Goodbye!")
            break

        if not user_input:
            continue

        # ── Built-in commands ─────────────────────────────────────────
        cmd = user_input.lower()

        if cmd in ("exit", "quit"):
            print("[system] Goodbye!")
            break

        if cmd == "reset":
            agent.reset_memory()
            print("[system] Conversation memory cleared.\n")
            continue

        if cmd == "debug":
            _toggle_debug()
            continue

        # ── Agent call ────────────────────────────────────────────────
        print()   # visual spacing
        try:
            answer = agent.chat(user_input)
            print(f"Agent: {answer}\n")

        except AuthenticationError:
            logger.error(
                "Authentication failed. Check your GROQ_API_KEY in .env."
            )
            print("[error] Invalid API key — please update your .env file.\n")

        except RateLimitError:
            logger.error("Rate limit reached after all retries.")
            print(
                "[error] Groq rate limit reached. "
                "Wait a moment and try again.\n"
            )

        except APIConnectionError as exc:
            logger.error("Connection error: %s", exc)
            print(
                "[error] Could not reach the Groq API. "
                "Check your internet connection.\n"
            )

        except APIStatusError as exc:
            logger.error("API status error %d: %s", exc.status_code, exc)
            print(f"[error] Groq API error ({exc.status_code}). Try again.\n")

        except RuntimeError as exc:
            logger.error("Agent runtime error: %s", exc)
            print(f"[error] {exc}\n")

        except Exception as exc:          # noqa: BLE001
            logger.exception("Unexpected error during agent.chat(): %s", exc)
            print(f"[error] Unexpected error: {exc}\n")


if __name__ == "__main__":
    main()
