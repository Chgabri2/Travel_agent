"""
main.py — SkyScout CLI entry point.

Run:
    python main.py

Replit users: set GROQ_API_KEY in the Secrets panel (padlock icon).
Others:       add GROQ_API_KEY=your_key to the .env file.
"""

import logging
import os
import sys

from dotenv import load_dotenv
from groq import AuthenticationError, RateLimitError, APIConnectionError, APIStatusError

from agent import GroqAgent

# ---------------------------------------------------------------------------
# Logging — stdout so Replit console and mobile both display it cleanly
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

BANNER = """
  ____  _          ____                     _
 / ___|| | ___   _/ ___|  ___ ___  _   _  | |_
 \\___ \\| |/ / | | \\___ \\ / __/ _ \\| | | | | __|
  ___) |   <| |_| |___) | (_| (_) | |_| | | |_
 |____/|_|\\_\\\\__, |____/ \\___\\___/ \\__,_|  \\__|
             |___/    AI Travel Agent

  Commands:  reset  debug  help  exit
  -----------------------------------------
"""

HELP_TEXT = """
Available commands:
  reset   - Clear conversation history and start fresh
  debug   - Toggle verbose debug logging on/off
  help    - Show this help message
  exit    - Quit SkyScout

Try asking:
  "Find me flights from Bangkok to London next Friday"
  "What are the cheapest dates to fly Bangkok to Tokyo?"
  "Do I need a visa to visit Japan as a Thai citizen?"
  "What is the baggage allowance on AirAsia?"
"""


def _toggle_debug() -> None:
    root = logging.getLogger()
    if root.level == logging.DEBUG:
        root.setLevel(logging.INFO)
        print("[system] Debug logging OFF.\n")
    else:
        root.setLevel(logging.DEBUG)
        print("[system] Debug logging ON.\n")


def _load_api_key() -> str:
    load_dotenv()
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        logger.error(
            "GROQ_API_KEY is not set. "
            "Add it to your .env file or the Replit Secrets panel."
        )
        sys.exit(1)
    return key


def main() -> None:
    api_key = _load_api_key()

    try:
        agent = GroqAgent(api_key=api_key)
    except Exception as exc:
        logger.critical("Failed to initialise SkyScout: %s", exc)
        sys.exit(1)

    print(BANNER)

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSafe travels! Goodbye.")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        if cmd in ("exit", "quit"):
            print("Safe travels! Goodbye.")
            break

        if cmd == "reset":
            agent.reset_memory()
            print("[system] Conversation cleared. Starting fresh!\n")
            continue

        if cmd == "debug":
            _toggle_debug()
            continue

        if cmd == "help":
            print(HELP_TEXT)
            continue

        print()
        try:
            answer = agent.chat(user_input)
            print(f"SkyScout: {answer}\n")

        except AuthenticationError:
            logger.error("Authentication failed - check your GROQ_API_KEY.")
            print("[error] Invalid API key. Update your .env or Replit Secret.\n")

        except RateLimitError:
            logger.error("Rate limit reached after all retries.")
            print("[error] Groq rate limit hit. Please wait a moment and try again.\n")

        except APIConnectionError as exc:
            logger.error("Connection error: %s", exc)
            print("[error] Cannot reach Groq API. Check your internet connection.\n")

        except APIStatusError as exc:
            logger.error("API status error %d: %s", exc.status_code, exc)
            print(f"[error] Groq API error ({exc.status_code}). Please try again.\n")

        except RuntimeError as exc:
            logger.error("Agent runtime error: %s", exc)
            print(f"[error] {exc}\n")

        except Exception as exc:
            logger.exception("Unexpected error: %s", exc)
            print(f"[error] Unexpected error: {exc}\n")


if __name__ == "__main__":
    main()
