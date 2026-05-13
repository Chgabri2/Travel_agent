# Single-Agent AI System

A clean, modular Python agent built on the **Anthropic API** (Claude) with
tool-calling, conversation memory, and a typed skill library.

---

## Project structure

```
single-agent/
├── agent.py          # AIAgent class — API calls, tool loop, memory
├── skills.py         # Skill library — functions, Pydantic schemas, dispatcher
├── main.py           # CLI entry point
├── .env.template     # Copy to .env and fill in your key
└── requirements.txt
```

---

## Quick start

```bash
# 1. Clone / copy the files, then enter the directory
cd single-agent

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your API key
cp .env.template .env
#  → open .env and replace the placeholder with your real key

# 5. Run
python main.py
```

---

## Built-in CLI commands

| Command  | Effect                          |
|----------|---------------------------------|
| `/tools` | List registered skills          |
| `/reset` | Clear conversation history      |
| `/quit`  | Exit (`/exit` or Ctrl-C also work) |

---

## Built-in skills

### `analyze_signal_data`
Accepts a list of floats and returns:
- Descriptive stats: mean, median, std dev, min, max, range
- Anomaly list: any sample whose absolute Z-score exceeds the threshold

Example prompt:
> "Analyse this signal: 1.2, 1.3, 1.1, 1.4, 9.8, 1.2, 1.3"

### `get_current_weather` *(mocked)*
Returns plausible-but-random weather data for any city.

Example prompt:
> "What's the weather like in Tokyo right now?"

---

## Adding a new skill

1. **Write the function** in `skills.py` with type hints + docstring.
2. **Create a Pydantic input model** for validation and schema generation.
3. **Append to `TOOL_DEFINITIONS`** — the schema is derived automatically via `_schema()`.
4. **Register in `_REGISTRY`** inside `dispatch_tool()`.

That's it — the agent picks it up automatically on the next run.

---

## Architecture notes

- **`AIAgent.chat()`** appends the user message, runs the agentic loop, and
  appends the final assistant reply — keeping `self.history` clean.
- **The agentic loop** (`_run_agentic_loop`) calls the API, detects
  `stop_reason == "tool_use"`, dispatches every tool-use block in parallel
  (within the same turn), appends results, and loops until the model
  returns a plain text response.
- **Pydantic models** serve dual purpose: they validate incoming tool
  arguments at runtime *and* auto-generate the `input_schema` JSON that
  the Anthropic API requires.
- **Error handling** covers API status errors, connection errors, unknown
  tool names, and Pydantic validation failures — all surfaced as readable
  messages rather than stack traces.
