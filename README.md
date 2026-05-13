# GroqAgent — ReAct AI Agent with Function Calling

A clean, modular Python agent that follows the **ReAct** (Reasoning + Acting)
pattern using the [Groq API](https://console.groq.com) and tool/function calling.

---

## Project layout

```
groq-agent/
├── agent.py          # GroqAgent class — ReAct loop, thread-safe memory
├── skills.py         # Tool definitions + dispatch registry
├── main.py           # CLI entry point
├── .env              # API key (git-ignored)
└── requirements.txt
```

---

## Quick start

### 1 — Install dependencies
```bash
pip install -r requirements.txt
```

### 2 — Set your API key
Edit `.env`:
```
GROQ_API_KEY=your_groq_api_key_here
```
Get a free key at <https://console.groq.com>.

> **Replit users**: add `GROQ_API_KEY` as a **Secret** in the Replit
> Secrets panel instead of editing `.env` — python-dotenv will pick it up
> automatically via `os.getenv`.

### 3 — Run
```bash
python main.py
```

---

## CLI commands

| Input    | Effect                                  |
|----------|-----------------------------------------|
| `reset`  | Clear conversation memory               |
| `debug`  | Toggle verbose debug logging            |
| `exit` / `quit` | Exit the program               |

---

## Available tools (skills.py)

| Tool | Description |
|------|-------------|
| `calculate_image_dimensions` | Computes scaled dimensions, aspect ratio, pixel count, and size category |
| `fetch_system_status` | Returns mock CPU, memory, disk, uptime, and health status |

### Adding a new tool

1. Write a function in `skills.py` with a detailed docstring.
2. Add its JSON schema to `TOOL_SCHEMAS`.
3. Register it in `TOOL_REGISTRY`.

That's it — the agent picks it up automatically.

---

## Architecture

```
main.py
  └─ GroqAgent.chat(user_message)
       └─ _react_loop()
            ├─ _call_api()          ← Groq /v1/chat/completions
            ├─ [finish="tool_calls"]
            │    └─ skills.dispatch(name, args)
            │         └─ tool result injected into memory
            └─ [finish="stop"]
                 └─ return final answer
```

The loop runs up to **6 rounds** before raising a `RuntimeError`, preventing
infinite tool-calling cycles.

---

## Models

Default: `llama-3.3-70b-versatile`  
Faster/cheaper: change `MODEL` in `agent.py` to `llama3-8b-8192`
