"""
tools/__init__.py

Central registry that merges every tool module.
agent.py imports only from here.

Adding a new tool module:
    1. Create  tools/my_module.py  with functions, SCHEMAS list, REGISTRY dict.
    2. Import and merge the two lines below — nothing else changes.
"""

import json
import logging
from typing import Any

from tools.flights    import SCHEMAS as _FLIGHT_SCHEMAS,  REGISTRY as _FLIGHT_REG
from tools.web_search import SCHEMAS as _WEB_SCHEMAS,     REGISTRY as _WEB_REG

logger = logging.getLogger(__name__)

# ── Merged schema list sent to Groq API ───────────────────────────────────
TOOL_SCHEMAS: list[dict[str, Any]] = [
    *_FLIGHT_SCHEMAS,
    *_WEB_SCHEMAS,
]

# ── Merged dispatch table: tool name → callable ───────────────────────────
TOOL_REGISTRY: dict[str, Any] = {
    **_FLIGHT_REG,
    **_WEB_REG,
}


def dispatch(tool_name: str, arguments: dict[str, Any]) -> str:
    """
    Invoke a registered tool by name and return the result as a JSON string.

    Args:
        tool_name:  Name of the tool to call (must be in TOOL_REGISTRY).
        arguments:  Keyword arguments forwarded to the tool function.

    Returns:
        JSON-encoded result string ready to insert as a 'tool' role message.

    Raises:
        KeyError: If tool_name is not registered.
    """
    if tool_name not in TOOL_REGISTRY:
        available = list(TOOL_REGISTRY.keys())
        raise KeyError(f"Unknown tool '{tool_name}'. Available: {available}")

    logger.info("→ Tool call  : %-25s | args: %s", tool_name, arguments)
    result      = TOOL_REGISTRY[tool_name](**arguments)
    json_result = json.dumps(result, indent=2, ensure_ascii=False)
    logger.info("← Tool result: %-25s | %.150s…", tool_name, json_result.replace("\n", " "))
    return json_result
