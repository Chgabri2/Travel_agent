# SkyScout — AI Travel Agent

A modular ReAct-pattern travel agent built on Groq + function calling.

## Structure

```
groq-agent/
├── agent.py          # GroqAgent class — loads skills.md, runs ReAct loop
├── skills.md         # Agent persona & tool-usage instructions (edit freely)
├── tools/
│   ├── __init__.py   # Merged registry — add modules here
│   ├── flights.py    # search_flights, get_flight_deals, get_airport_info
│   └── web_search.py # search_web (DuckDuckGo, no API key needed)
├── main.py           # CLI entry point
├── .env              # GROQ_API_KEY
└── requirements.txt
```

## Quick start

```bash
pip install -r requirements.txt
# Add GROQ_API_KEY to .env or Replit Secrets panel
python main.py
```

## How it works

1. `agent.py` reads `skills.md` at startup and uses it as the system prompt.
2. The user's message triggers the ReAct loop: the model reasons, calls tools, observes results, and repeats until it has a final answer.
3. Tools live in `tools/` — each module exports `SCHEMAS` and `REGISTRY`.
4. `tools/__init__.py` merges everything; `agent.py` never imports individual modules.

## Customising

- **Change the agent's personality or instructions**: edit `skills.md` only.
- **Add a new tool**: create `tools/my_tool.py` with functions + `SCHEMAS` + `REGISTRY`, then import and merge in `tools/__init__.py`.
- **Switch model**: change `MODEL` in `agent.py`.

## CLI commands

| Command | Effect |
|---------|--------|
| `reset` | Clear conversation history |
| `debug` | Toggle verbose logging |
| `help`  | Show example prompts |
| `exit`  | Quit |

## Example prompts

- "Find flights from Bangkok to London on 2025-08-15, 2 passengers"
- "When is the cheapest time to fly from Koh Samui to Singapore?"
- "Do I need a visa for Japan as a Thai passport holder?"
- "What is AirAsia's baggage policy?"
