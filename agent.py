"""
agent.py — GroqAgent: a ReAct-pattern AI agent backed by the Groq API.

ReAct loop (per turn):
    Thought → the LLM decides what to do next.
    Action  → the LLM emits a tool_call (or stops).
    Observe → we run the tool and feed the result back.
    ...repeat until the model produces a plain text final answer.
"""

import json
import logging
import threading
import time
from typing import Any

from groq import Groq, RateLimitError, APIStatusError, APIConnectionError
from groq.types.chat import ChatCompletion

from skills import TOOL_SCHEMAS, dispatch

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL            = "llama-3.3-70b-versatile"   # fallback: "llama3-8b-8192"
MAX_TOOL_ROUNDS  = 6    # hard cap on Thought→Action→Observe iterations
MAX_RETRIES      = 3    # Groq API call retries on transient errors
RETRY_BASE_DELAY = 2.0  # seconds, exponential back-off base

SYSTEM_PROMPT = """You are a helpful, precise AI assistant with access to tools.

Follow the ReAct pattern strictly:
1. THINK  — reason briefly about what the user needs.
2. ACT    — call a tool if required, OR produce a final answer.
3. OBSERVE— after receiving a tool result, reason about it, then act again or answer.

Rules:
- Never fabricate tool results; always wait for the actual tool output.
- When you have enough information, respond directly without calling more tools.
- Keep tool calls focused: pass only the arguments the schema requires.
- Be concise and factual in your final answers.
"""


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class GroqAgent:
    """
    A thread-safe conversational agent that uses Groq function-calling
    to reason over tools before producing a final answer.

    Attributes:
        client   (Groq):       Authenticated Groq API client.
        model    (str):        Model identifier used for completions.
        memory   (list[dict]): Conversation history (system + turns).
        _lock    (Lock):       Guards memory for concurrent access.
    """

    def __init__(self, api_key: str, model: str = MODEL) -> None:
        """
        Initialise the agent.

        Args:
            api_key: Groq API key (loaded from .env by the caller).
            model:   Groq model string. Defaults to llama-3.3-70b-versatile.
        """
        self.client: Groq       = Groq(api_key=api_key)
        self.model:  str        = model
        self._lock:  threading.Lock = threading.Lock()
        self.memory: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        logger.info("GroqAgent initialised | model=%s", self.model)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(self, user_message: str) -> str:
        """
        Send a user message and return the agent's final answer.

        Internally runs the full ReAct loop (tool calls → observations →
        final response).  Thread-safe: concurrent callers each get their
        own serialised access to shared memory.

        Args:
            user_message: Plain-text input from the user.

        Returns:
            The agent's final plain-text answer.
        """
        with self._lock:
            self._add_message("user", user_message)
            answer = self._react_loop()
            return answer

    def reset_memory(self) -> None:
        """Clear conversation history, keeping the system prompt."""
        with self._lock:
            self.memory = [self.memory[0]]   # keep system prompt
        logger.info("Conversation memory reset.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_message(self, role: str, content: str) -> None:
        """Append a message dict to memory (caller holds the lock)."""
        self.memory.append({"role": role, "content": content})

    def _react_loop(self) -> str:
        """
        Core ReAct loop.  Runs inside the lock held by chat().

        Returns:
            The model's final text answer.

        Raises:
            RuntimeError: If the maximum tool rounds are exceeded without
                          a text answer.
        """
        for round_num in range(1, MAX_TOOL_ROUNDS + 1):
            logger.debug("ReAct round %d/%d", round_num, MAX_TOOL_ROUNDS)

            response = self._call_api()
            choice   = response.choices[0]
            message  = choice.message

            # ── 1. Persist assistant turn ──────────────────────────────
            assistant_msg: dict[str, Any] = {"role": "assistant"}

            if message.content:
                assistant_msg["content"] = message.content
            else:
                assistant_msg["content"] = None   # required by some models

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

            # ── 2. Check finish reason ─────────────────────────────────
            finish = choice.finish_reason
            logger.debug("finish_reason=%s", finish)

            if finish == "stop":
                # Model produced a plain-text final answer.
                final = message.content or ""
                logger.info("Agent answered after %d round(s).", round_num)
                return final.strip()

            if finish == "tool_calls" and message.tool_calls:
                # ── 3. Execute each tool call (Action → Observe) ───────
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        raw_args  = tool_call.function.arguments or "{}"
                        arguments = json.loads(raw_args)
                    except json.JSONDecodeError as exc:
                        logger.error("Failed to parse tool arguments: %s", exc)
                        arguments = {}

                    logger.info(
                        "Tool call → name='%s' | args=%s", tool_name, arguments
                    )

                    try:
                        tool_result = dispatch(tool_name, arguments)
                        logger.info(
                            "Tool result ← name='%s' | result=%s",
                            tool_name, tool_result[:200],
                        )
                    except Exception as exc:          # noqa: BLE001
                        tool_result = json.dumps({"error": str(exc)})
                        logger.warning(
                            "Tool '%s' raised an error: %s", tool_name, exc
                        )

                    # Inject tool result into memory
                    self.memory.append({
                        "role":         "tool",
                        "tool_call_id": tool_call.id,
                        "content":      tool_result,
                    })

                # Continue loop → model will now "Observe" and decide next step
                continue

            # ── 4. Unexpected finish reason ────────────────────────────
            logger.warning("Unexpected finish_reason: %s", finish)
            fallback = message.content or "I'm not sure how to respond."
            return fallback.strip()

        # Exceeded max rounds without a stop
        logger.error("Max tool rounds (%d) exceeded.", MAX_TOOL_ROUNDS)
        raise RuntimeError(
            f"Agent exceeded the maximum of {MAX_TOOL_ROUNDS} tool-call rounds "
            "without producing a final answer."
        )

    def _call_api(self) -> ChatCompletion:
        """
        Call the Groq completions endpoint with exponential back-off retry.

        Returns:
            A ChatCompletion object from the Groq SDK.

        Raises:
            RateLimitError:      After all retries are exhausted.
            APIConnectionError:  After all retries are exhausted.
            APIStatusError:      For non-retryable server errors.
        """
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response: ChatCompletion = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.memory,       # type: ignore[arg-type]
                    tools=TOOL_SCHEMAS,         # type: ignore[arg-type]
                    tool_choice="auto",
                    temperature=0.2,
                    max_tokens=2048,
                )
                return response

            except RateLimitError as exc:
                delay = RETRY_BASE_DELAY ** attempt
                logger.warning(
                    "Rate limit hit (attempt %d/%d). Retrying in %.1fs…",
                    attempt, MAX_RETRIES, delay,
                )
                if attempt == MAX_RETRIES:
                    raise
                time.sleep(delay)

            except APIConnectionError as exc:
                delay = RETRY_BASE_DELAY ** attempt
                logger.warning(
                    "Connection error (attempt %d/%d): %s. Retrying in %.1fs…",
                    attempt, MAX_RETRIES, exc, delay,
                )
                if attempt == MAX_RETRIES:
                    raise
                time.sleep(delay)

            except APIStatusError as exc:
                # 5xx errors are potentially transient; 4xx are not
                if exc.status_code and exc.status_code >= 500:
                    delay = RETRY_BASE_DELAY ** attempt
                    logger.warning(
                        "Server error %d (attempt %d/%d). Retrying in %.1fs…",
                        exc.status_code, attempt, MAX_RETRIES, delay,
                    )
                    if attempt == MAX_RETRIES:
                        raise
                    time.sleep(delay)
                else:
                    logger.error("Non-retryable API error %d: %s", exc.status_code, exc)
                    raise

        # Should never reach here, but satisfies the type checker
        raise RuntimeError("_call_api exhausted all retries unexpectedly.")
