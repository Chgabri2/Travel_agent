"""
agent.py
--------
Core AIAgent class that manages communication with the Anthropic API,
handles tool-calling loops, and maintains conversation memory.
"""

import json
import os
from typing import Any

import anthropic
from dotenv import load_dotenv

from skills import TOOL_DEFINITIONS, dispatch_tool

load_dotenv()

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096


class AIAgent:
    """
    A single-agent system backed by Claude via the Anthropic API.

    The agent maintains a rolling conversation history and automatically
    resolves tool-call / tool-result cycles until the model produces a
    final text response.

    Attributes:
        client:  Authenticated Anthropic client.
        history: List of message dicts that form the conversation context.
        system:  System-prompt string injected on every API request.
    """

    def __init__(self, system_prompt: str = "") -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY is not set. "
                "Copy .env.template to .env and add your key."
            )

        self.client = anthropic.Anthropic(api_key=api_key)
        self.system: str = system_prompt or (
            "You are a helpful AI assistant with access to a set of tools. "
            "Use the tools when they are relevant to the user's request. "
            "Always explain what you are doing in plain language."
        )
        self.history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def chat(self, user_message: str) -> str:
        """
        Send a user message, resolve any tool calls, and return the
        assistant's final text reply.

        Args:
            user_message: Raw text from the user.

        Returns:
            The assistant's final plain-text response.
        """
        self.history.append({"role": "user", "content": user_message})

        try:
            reply = self._run_agentic_loop()
        except anthropic.APIStatusError as exc:
            reply = f"[API error {exc.status_code}]: {exc.message}"
        except anthropic.APIConnectionError:
            reply = "[Connection error]: Could not reach the Anthropic API."
        except Exception as exc:  # noqa: BLE001
            reply = f"[Unexpected error]: {exc}"

        self.history.append({"role": "assistant", "content": reply})
        return reply

    def reset(self) -> None:
        """Clear conversation history (keeps system prompt)."""
        self.history.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_agentic_loop(self) -> str:
        """
        Repeatedly call the API until the model stops requesting tool use.

        Returns:
            The final text produced by the model.
        """
        # We keep a *working* copy of history so partial tool exchanges
        # are visible to the model but we only append the final assistant
        # text to self.history once.
        working_history = list(self.history)

        while True:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=self.system,
                tools=TOOL_DEFINITIONS,
                messages=working_history,
            )

            # ── Model wants to call one or more tools ──────────────────
            if response.stop_reason == "tool_use":
                # Collect the full assistant turn (may mix text + tool_use blocks)
                assistant_turn = {"role": "assistant", "content": response.content}
                working_history.append(assistant_turn)

                # Build the tool_result turn
                tool_results = self._execute_tool_calls(response.content)
                working_history.append(
                    {"role": "user", "content": tool_results}
                )
                continue  # ask the model again with the results

            # ── Model produced a final text response ───────────────────
            text_blocks = [
                block.text
                for block in response.content
                if hasattr(block, "text")
            ]
            return "\n".join(text_blocks).strip()

    def _execute_tool_calls(
        self, content_blocks: list[Any]
    ) -> list[dict[str, Any]]:
        """
        Iterate over tool_use blocks, dispatch each call, and return a
        list of tool_result content items ready to send back to the API.

        Args:
            content_blocks: The ``response.content`` list from the API.

        Returns:
            A list of tool_result dicts.
        """
        results: list[dict[str, Any]] = []

        for block in content_blocks:
            if block.type != "tool_use":
                continue

            tool_id: str = block.id
            tool_name: str = block.name
            tool_input: dict[str, Any] = block.input or {}

            print(f"\n  🔧  Tool called : {tool_name}")
            print(f"      Input       : {json.dumps(tool_input, indent=6)}")

            try:
                output = dispatch_tool(tool_name, tool_input)
                is_error = False
            except Exception as exc:  # noqa: BLE001
                output = f"Tool execution failed: {exc}"
                is_error = True

            print(f"      Output      : {json.dumps(output, indent=6)}\n")

            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": json.dumps(output),
                    "is_error": is_error,
                }
            )

        return results
