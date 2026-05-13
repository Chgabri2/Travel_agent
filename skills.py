"""
skills.py
---------
Library of callable skills (tools) exposed to the AIAgent.

Each public function:
  • Has full type hints.
  • Has a detailed docstring (used verbatim by the LLM).
  • Is registered in TOOL_DEFINITIONS (Anthropic tool-use format).
  • Is reachable via dispatch_tool().

Adding a new skill:
  1. Write the function with type hints + docstring.
  2. Add a Pydantic model for its input schema.
  3. Append an entry to TOOL_DEFINITIONS.
  4. Add a case to dispatch_tool().
"""

import math
import random
import statistics
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ══════════════════════════════════════════════════════════════════════
# Pydantic input schemas  (used both for validation and JSON-schema gen)
# ══════════════════════════════════════════════════════════════════════

class AnalyzeSignalDataInput(BaseModel):
    """Input schema for analyze_signal_data."""

    data: list[float] = Field(
        ...,
        description="Ordered sequence of numeric signal samples to analyse.",
        min_length=2,
    )
    z_threshold: float = Field(
        default=2.5,
        description=(
            "Z-score threshold above which a sample is flagged as an anomaly. "
            "Defaults to 2.5."
        ),
        gt=0,
    )

    @field_validator("data")
    @classmethod
    def no_nan_inf(cls, v: list[float]) -> list[float]:
        for x in v:
            if not math.isfinite(x):
                raise ValueError("data must not contain NaN or Inf values.")
        return v


class GetCurrentWeatherInput(BaseModel):
    """Input schema for get_current_weather."""

    location: str = Field(
        ...,
        description=(
            "City and optional country/state, e.g. 'Paris, France' "
            "or 'Austin, TX'."
        ),
        min_length=2,
    )
    unit: str = Field(
        default="celsius",
        description="Temperature unit: 'celsius' or 'fahrenheit'.",
        pattern="^(celsius|fahrenheit)$",
    )


# ══════════════════════════════════════════════════════════════════════
# Skill implementations
# ══════════════════════════════════════════════════════════════════════

def analyze_signal_data(
    data: list[float],
    z_threshold: float = 2.5,
) -> dict[str, Any]:
    """
    Analyse a 1-D numeric signal and return descriptive statistics plus
    any detected anomalies.

    The function computes mean, median, standard deviation, min, max, and
    range.  It then flags samples whose absolute Z-score exceeds
    *z_threshold* as anomalies, returning their index and value.

    Args:
        data:        Ordered list of numeric signal samples (≥ 2 values,
                     no NaN / Inf).
        z_threshold: Samples with |z| > this value are marked as
                     anomalies.  Defaults to 2.5.

    Returns:
        A dict with keys:
          - ``count``       – number of samples
          - ``mean``        – arithmetic mean
          - ``median``      – median value
          - ``std_dev``     – population standard deviation
          - ``minimum``     – smallest value
          - ``maximum``     – largest value
          - ``range``       – maximum − minimum
          - ``anomalies``   – list of {index, value, z_score} for outliers
          - ``anomaly_count`` – total number of anomalies found
    """
    validated = AnalyzeSignalDataInput(data=data, z_threshold=z_threshold)
    d = validated.data
    n = len(d)

    mean = statistics.mean(d)
    median = statistics.median(d)
    std_dev = statistics.pstdev(d)  # population std dev

    anomalies: list[dict[str, Any]] = []
    if std_dev > 0:
        for i, val in enumerate(d):
            z = (val - mean) / std_dev
            if abs(z) > validated.z_threshold:
                anomalies.append(
                    {"index": i, "value": round(val, 6), "z_score": round(z, 4)}
                )

    return {
        "count": n,
        "mean": round(mean, 6),
        "median": round(median, 6),
        "std_dev": round(std_dev, 6),
        "minimum": round(min(d), 6),
        "maximum": round(max(d), 6),
        "range": round(max(d) - min(d), 6),
        "anomalies": anomalies,
        "anomaly_count": len(anomalies),
    }


def get_current_weather(
    location: str,
    unit: str = "celsius",
) -> dict[str, Any]:
    """
    Return the *mocked* current weather for a given location.

    This is a wildcard / demonstration skill.  In production you would
    replace the body with a real weather-API call (e.g. OpenWeatherMap).
    The mock returns plausible but randomly generated values so the agent
    can demonstrate tool-calling end-to-end without external credentials.

    Args:
        location: City name, optionally with country/state suffix,
                  e.g. ``"London, UK"`` or ``"New York, NY"``.
        unit:     ``"celsius"`` (default) or ``"fahrenheit"``.

    Returns:
        A dict with keys:
          - ``location``    – echoed back location string
          - ``temperature`` – numeric temperature (rounded to 1 dp)
          - ``unit``        – temperature unit used
          - ``condition``   – short weather description
          - ``humidity_pct``– relative humidity percentage (0–100)
          - ``wind_kph``    – wind speed in km/h
          - ``source``      – always ``"mock"`` for this implementation
    """
    validated = GetCurrentWeatherInput(location=location, unit=unit)

    conditions = [
        "Sunny", "Partly cloudy", "Overcast", "Light rain",
        "Thunderstorms", "Foggy", "Windy", "Clear skies",
    ]

    temp_c = round(random.uniform(-5, 38), 1)
    temp = (
        temp_c
        if validated.unit == "celsius"
        else round(temp_c * 9 / 5 + 32, 1)
    )

    return {
        "location": validated.location,
        "temperature": temp,
        "unit": validated.unit,
        "condition": random.choice(conditions),
        "humidity_pct": random.randint(20, 95),
        "wind_kph": round(random.uniform(0, 80), 1),
        "source": "mock",
    }


# ══════════════════════════════════════════════════════════════════════
# Tool definitions  (Anthropic tool-use format, schemas auto-derived)
# ══════════════════════════════════════════════════════════════════════

def _schema(model: type[BaseModel]) -> dict[str, Any]:
    """Return a clean JSON-schema dict from a Pydantic model."""
    raw = model.model_json_schema()
    # Strip the top-level title; Anthropic doesn't need it.
    raw.pop("title", None)
    return raw


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "analyze_signal_data",
        "description": (
            "Analyse a 1-D numeric signal (list of floats) and return "
            "descriptive statistics (mean, median, std dev, min, max, range) "
            "together with a list of anomalous samples detected via Z-score "
            "thresholding.  Use this whenever the user wants statistical "
            "analysis or anomaly/outlier detection on numeric data."
        ),
        "input_schema": _schema(AnalyzeSignalDataInput),
    },
    {
        "name": "get_current_weather",
        "description": (
            "Retrieve the current weather conditions for any city or location. "
            "Returns temperature, weather condition, humidity, and wind speed. "
            "Use this when the user asks about weather, temperature, or "
            "climate conditions in a specific place."
        ),
        "input_schema": _schema(GetCurrentWeatherInput),
    },
]


# ══════════════════════════════════════════════════════════════════════
# Dispatcher
# ══════════════════════════════════════════════════════════════════════

_REGISTRY: dict[str, Any] = {
    "analyze_signal_data": analyze_signal_data,
    "get_current_weather": get_current_weather,
}


def dispatch_tool(name: str, inputs: dict[str, Any]) -> Any:
    """
    Dispatch a tool call by name with the provided inputs.

    Args:
        name:   The tool name as returned by the API (e.g. ``"get_current_weather"``).
        inputs: Raw dict of arguments from the model's tool_use block.

    Returns:
        Whatever the underlying skill function returns.

    Raises:
        ValueError: If *name* does not match any registered skill.
        pydantic.ValidationError: If *inputs* fail schema validation inside
                                   the skill.
    """
    fn = _REGISTRY.get(name)
    if fn is None:
        known = ", ".join(_REGISTRY)
        raise ValueError(
            f"Unknown tool '{name}'. Registered tools: {known}"
        )
    return fn(**inputs)
