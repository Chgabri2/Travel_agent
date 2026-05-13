"""
agent.py — SkyScout GroqAgent.

Loads skills.md as the system prompt, then runs the ReAct loop
(Thought → Action → Observe → repeat) until a final answer is produced.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from groq import (
    Groq,
    RateLimitError,
    APIStatusError,
    APIConnectionError,
)
from groq.types.chat import ChatCompletion

from tools import TOOL_SCHEMAS, dispatch

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL            = "llama-3.3-70b-versatile"
MAX_TOOL_ROUNDS  = 8       # max Thought→Action→Observe iterations per turn
MAX_RETRIES      = 3       # Groq API retries on transient errors
RETRY_BASE_DELAY = 2.0     # seconds (exponential back-off base)
SKILLS_FILE      = Path(__file__).parent / "skills.md"


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class GroqAgent:
    """
    SkyScout — a travel-focused AI agent powered by Groq + function calling.

    The agent's persona and tool-usage guidance live in skills.md,
    which is loaded once at startup and injected as the system prompt.
    All tool implementations are in the tools/ package.

    Attributes:
        client  (Groq):            Authenticated Groq client.
        model   (str):             Model identifier.
        memory  (list[dict]):      Full conversation history.
        _lock   (threading.Lock):  Guards memory for thread-safe access.
    """

    def __init__(self, api_key: str, model: str = MODEL) -> None:
        self.client = Groq(api_key=api_key)
        self.model  = model
        self._lock  = threading.Lock()

        system_prompt = self._load_skills_md()
        self.memory: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]
        logger.info("SkyScout initialised | model=%s | tools=%d",
                    self.model, len(TOOL_SCHEMAS))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def chat(self, user_message: str) -> str:
        """Process one user turn and return the agent's final answer."""
        with self._lock:
            self.memory.append({"role": "user", "content": user_message})
            return self._react_loop()

    def reset_memory(self) -> None:
        """Clear conversation history, keeping the system prompt."""
        with self._lock:
            self.memory = [self.memory[0]]
        logger.info("Conversation memory reset.")

    # ------------------------------------------------------------------
    # Internal: skills loader
    # ------------------------------------------------------------------

    @staticmethod
    def _load_skills_md() -> str:
        """Read skills.md and return its content as the system prompt."""
        if SKILLS_FILE.exists():
            content = SKILLS_FILE.read_text(encoding="utf-8").strip()
            logger.info("Loaded system prompt from %s (%d chars)", SKILLS_FILE, len(content))
            return content

        logger.warning(
            "skills.md not found at %s — using minimal fallback prompt.", SKILLS_FILE
        )
        return (
            "You are SkyScout, a helpful AI travel agent. "
            "Help users find flights and travel deals. "
            "Use available tools to search for real information."
        )

    # ------------------------------------------------------------------
    # Internal: ReAct loop
    # ------------------------------------------------------------------

    def _react_loop(self) -> str:
        """Core ReAct (Reason + Act) loop — runs inside the lock held by chat()."""
        for round_num in range(1, MAX_TOOL_ROUNDS + 1):
            logger.debug("ReAct round %d / %d", round_num, MAX_TOOL_ROUNDS)

            response = self._call_groq_api()
            choice   = response.choices[0]
            message  = choice.message
            finish   = choice.finish_reason

            # ── Persist assistant message ──────────────────────────────
            assistant_msg: dict[str, Any] = {
                "role":    "assistant",
                "content": message.content,
            }
            if message.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id":   tc.id,
                        "type": "function",
                        "function": {
                            "name":      tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ]
            self.memory.append(assistant_msg)

            logger.debug("finish_reason=%s", finish)

            # ── Final answer ───────────────────────────────────────────
            if finish == "stop":
                answer = (message.content or "").strip()
                logger.info("Final answer produced after %d round(s).", round_num)
                return answer

            # ── Tool calls ─────────────────────────────────────────────
            if finish == "tool_calls" and message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments or "{}")
                    except json.JSONDecodeError:
                        logger.error("Bad JSON in tool arguments for '%s'", tool_name)
                        arguments = {}

                    try:
                        tool_result = dispatch(tool_name, arguments)
                    except Exception as exc:               # noqa: BLE001
                        tool_result = json.dumps({"error": str(exc)})
                        logger.warning("Tool '%s' raised: %s", tool_name, exc)

                    self.memory.append({
                        "role":         "tool",
                        "tool_call_id": tool_call.id,
                        "content":      tool_result,
                    })
                continue

            # ── Unexpected finish reason ───────────────────────────────
            logger.warning("Unexpected finish_reason: %s", finish)
            return (message.content or "I encountered an unexpected state.").strip()

        logger.error("MAX_TOOL_ROUNDS (%d) exceeded.", MAX_TOOL_ROUNDS)
        raise RuntimeError(
            f"Agent exceeded {MAX_TOOL_ROUNDS} reasoning rounds without a final answer."
        )

    # ------------------------------------------------------------------
    # Internal: Groq API call with retry
    # ------------------------------------------------------------------

    def _call_groq_api(self) -> ChatCompletion:
        """Call the Groq chat completions endpoint with exponential back-off."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=self.memory,          # type: ignore[arg-type]
                    tools=TOOL_SCHEMAS,            # type: ignore[arg-type]
                    tool_choice="auto",
                    temperature=0.3,
                    max_tokens=2048,
                )

            except RateLimitError:
                delay = RETRY_BASE_DELAY ** attempt
                logger.warning("Rate limit (attempt %d/%d) — retrying in %.1fs…",
                               attempt, MAX_RETRIES, delay)
                if attempt == MAX_RETRIES:
                    raise
                time.sleep(delay)

            except APIConnectionError as exc:
                delay = RETRY_BASE_DELAY ** attempt
                logger.warning("Connection error (attempt %d/%d): %s — retrying in %.1fs…",
                               attempt, MAX_RETRIES, exc, delay)
                if attempt == MAX_RETRIES:
                    raise
                time.sleep(delay)

            except APIStatusError as exc:
                if exc.status_code and exc.status_code >= 500:
                    delay = RETRY_BASE_DELAY ** attempt
                    logger.warning("Server error %d (attempt %d/%d) — retrying in %.1fs…",
                                   exc.status_code, attempt, MAX_RETRIES, delay)
                    if attempt == MAX_RETRIES:
                        raise
                    time.sleep(delay)
                else:
                    logger.error("API error %d: %s", exc.status_code, exc)
                    raise

        raise RuntimeError("_call_groq_api: all retries exhausted.")
