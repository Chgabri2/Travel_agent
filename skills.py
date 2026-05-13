"""
skills.py — Tool definitions for the GroqAgent.

Each function is a "skill" the agent can invoke. The docstring is parsed
into the tool schema that Groq/OpenAI-format APIs understand, so keep them
precise and descriptive.
"""

import json
import logging
import platform
import random
import time
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Skill implementations
# ---------------------------------------------------------------------------

def calculate_image_dimensions(
    width: int,
    height: int,
    scale_factor: float = 1.0,
) -> dict[str, Any]:
    """
    Calculate scaled image dimensions and derived metadata for vision tasks.

    Given an original width and height (in pixels) and an optional scale
    factor, this tool returns the new dimensions, aspect ratio, total pixel
    count, and a human-readable size category.  Use it whenever you need to
    reason about image geometry before processing or displaying an image.

    Args:
        width:        Original image width in pixels  (must be > 0).
        height:       Original image height in pixels (must be > 0).
        scale_factor: Multiplier applied to both dimensions. Default is 1.0
                      (no scaling).  Use 0.5 to halve, 2.0 to double, etc.

    Returns:
        A dict with keys:
            original_width, original_height,
            scaled_width,   scaled_height,
            aspect_ratio    (rounded to 4 dp),
            total_pixels    (scaled),
            size_category   ("thumbnail" | "small" | "medium" | "large" | "ultra"),
            scale_factor_applied.
    """
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive integers.")
    if scale_factor <= 0:
        raise ValueError("scale_factor must be a positive number.")

    scaled_w = int(width * scale_factor)
    scaled_h = int(height * scale_factor)
    aspect   = round(scaled_w / scaled_h, 4)
    pixels   = scaled_w * scaled_h

    if pixels < 10_000:
        category = "thumbnail"
    elif pixels < 250_000:
        category = "small"
    elif pixels < 2_000_000:
        category = "medium"
    elif pixels < 8_000_000:
        category = "large"
    else:
        category = "ultra"

    result = {
        "original_width":      width,
        "original_height":     height,
        "scaled_width":        scaled_w,
        "scaled_height":       scaled_h,
        "aspect_ratio":        aspect,
        "total_pixels":        pixels,
        "size_category":       category,
        "scale_factor_applied": scale_factor,
    }
    logger.debug("calculate_image_dimensions result: %s", result)
    return result


def fetch_system_status() -> dict[str, Any]:
    """
    Return a snapshot of the current host system's resource utilisation.

    This tool provides mock (simulated) CPU usage, memory stats, disk usage,
    process uptime, and basic OS information.  Call it when the user asks
    about system health, resource consumption, or server status.

    Args:
        None — this tool takes no arguments.

    Returns:
        A dict with keys:
            cpu_usage_percent   (float, 0–100),
            memory_total_mb     (int),
            memory_used_mb      (int),
            memory_free_mb      (int),
            memory_used_percent (float),
            disk_total_gb       (int),
            disk_used_gb        (int),
            disk_free_gb        (int),
            uptime_seconds      (int),
            uptime_human        (str, e.g. "2h 14m 33s"),
            os_info             (str),
            status              ("healthy" | "warning" | "critical").
    """
    # --- Simulated / mock values (safe for Replit sandbox) ---
    cpu     = round(random.uniform(5.0, 85.0), 1)
    mem_tot = 2048          # MB  (typical Replit free tier)
    mem_use = random.randint(400, 1600)
    mem_fre = mem_tot - mem_use
    dsk_tot = 50            # GB
    dsk_use = random.randint(5, 35)
    dsk_fre = dsk_tot - dsk_use
    uptime  = random.randint(60, 86_400)

    hours, rem  = divmod(uptime, 3600)
    minutes, sec = divmod(rem, 60)
    uptime_human = f"{hours}h {minutes}m {sec}s"

    mem_pct = round((mem_use / mem_tot) * 100, 1)

    if cpu > 80 or mem_pct > 85:
        status = "critical"
    elif cpu > 60 or mem_pct > 65:
        status = "warning"
    else:
        status = "healthy"

    result = {
        "cpu_usage_percent":   cpu,
        "memory_total_mb":     mem_tot,
        "memory_used_mb":      mem_use,
        "memory_free_mb":      mem_fre,
        "memory_used_percent": mem_pct,
        "disk_total_gb":       dsk_tot,
        "disk_used_gb":        dsk_use,
        "disk_free_gb":        dsk_fre,
        "uptime_seconds":      uptime,
        "uptime_human":        uptime_human,
        "os_info":             f"{platform.system()} {platform.release()}",
        "status":              status,
    }
    logger.debug("fetch_system_status result: %s", result)
    return result


# ---------------------------------------------------------------------------
# Registry — maps name → (callable, JSON schema)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "calculate_image_dimensions",
            "description": (
                "Calculate scaled image dimensions and derived metadata "
                "(aspect ratio, pixel count, size category) for vision tasks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "width": {
                        "type": "integer",
                        "description": "Original image width in pixels (must be > 0).",
                    },
                    "height": {
                        "type": "integer",
                        "description": "Original image height in pixels (must be > 0).",
                    },
                    "scale_factor": {
                        "type": "number",
                        "description": (
                            "Multiplier for both dimensions. "
                            "Default 1.0 (no scaling). Use 0.5 to halve, 2.0 to double."
                        ),
                        "default": 1.0,
                    },
                },
                "required": ["width", "height"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_system_status",
            "description": (
                "Return a snapshot of host system resource utilisation: "
                "CPU, memory, disk, uptime, and overall health status."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]

# Dispatch table: tool name → Python callable
TOOL_REGISTRY: dict[str, Any] = {
    "calculate_image_dimensions": calculate_image_dimensions,
    "fetch_system_status":        fetch_system_status,
}


def dispatch(tool_name: str, arguments: dict[str, Any]) -> str:
    """
    Invoke a registered tool by name and return its result as a JSON string.

    Args:
        tool_name:  The name of the tool to call (must exist in TOOL_REGISTRY).
        arguments:  Keyword arguments to pass to the tool function.

    Returns:
        JSON-encoded string of the tool's return value.

    Raises:
        KeyError:  If the tool name is not registered.
        Exception: Re-raises any exception thrown by the underlying tool.
    """
    if tool_name not in TOOL_REGISTRY:
        raise KeyError(f"Unknown tool: '{tool_name}'. Available: {list(TOOL_REGISTRY)}")

    logger.info("Dispatching tool '%s' with args: %s", tool_name, arguments)
    func   = TOOL_REGISTRY[tool_name]
    result = func(**arguments)
    return json.dumps(result, indent=2)
