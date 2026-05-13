"""
tools/web_search.py — Live web search using DuckDuckGo.

No API key required. Works on Replit out of the box.
Install: pip install duckduckgo-search
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------

def search_web(query: str, max_results: int = 5) -> dict[str, Any]:
    """
    Search the web using DuckDuckGo and return the top results.

    Use this tool for any question that requires current or real-world
    information: visa requirements, travel advisories, airline policies,
    baggage rules, COVID / entry restrictions, current events, or any
    topic where up-to-date data matters.

    Args:
        query:       The search query string (be specific for better results).
        max_results: Maximum number of results to return (1–10, default 5).

    Returns:
        Dict with keys:
            query (str), results_count (int), results (list of dicts with
            keys: title, url, snippet).
        On failure, returns a dict with an "error" key.
    """
    max_results = max(1, min(max_results, 10))   # clamp 1–10

    try:
        from duckduckgo_search import DDGS          # lazy import
    except ImportError:
        return {
            "error": (
                "duckduckgo-search is not installed. "
                "Run: pip install duckduckgo-search"
            )
        }

    try:
        with DDGS() as ddgs:
            raw = ddgs.text(query, max_results=max_results)

        results: list[dict[str, str]] = []
        for item in raw:
            results.append({
                "title":   item.get("title",   ""),
                "url":     item.get("href",    ""),
                "snippet": item.get("body",    ""),
            })

        logger.debug("search_web: query=%r returned %d results", query, len(results))

        return {
            "query":         query,
            "results_count": len(results),
            "results":       results,
        }

    except Exception as exc:                       # noqa: BLE001
        logger.error("search_web failed: %s", exc)
        return {
            "error":   f"Web search failed: {exc}",
            "query":   query,
            "results": [],
        }


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Search the live web using DuckDuckGo. Use for current, "
                "real-world information: visa requirements, travel advisories, "
                "airline baggage policies, entry restrictions, travel news, "
                "or any topic needing up-to-date data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Specific search query. For travel topics include "
                            "the country/airline name for precise results, "
                            "e.g. 'Thailand visa requirements for UK citizens 2024'."
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Number of results to return (1–10). Default is 5.",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
]

REGISTRY: dict[str, Any] = {
    "search_web": search_web,
}
