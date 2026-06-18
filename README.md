# Eloys CLI Chatbot

A Python CLI chatbot powered by Claude with tool-use support for weather lookups and topic research via an external API.

## Requirements

- Python 3.11+
- An Anthropic API key

## Install

```bash
cd Eloys
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Environment

Create a `.env` file from the template:

```bash
cp .env.example .env
```

Then set your Anthropic API key:

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

## Run

```bash
python main.py
```

Type `quit`, `exit`, or `q` to stop. Press `Ctrl+C` at any input prompt to exit cleanly.

## Tools

| Tool | Trigger | Behaviour |
|---|---|---|
| `get_weather` | Questions about current weather | Calls the external weather endpoint; fast, no cancel UI |
| `research_topic` | Research / deep-dive requests | Shows a live spinner; press `Ctrl+C` to cancel mid-request |

Research results are cached in memory for 5 minutes — a repeated query returns instantly.

See [DISCOVERY.md](DISCOVERY.md) for the API behaviours found during development and how the code handles them.

## Example interactions

Weather:
```
You: What's the weather in Tokyo?
Assistant: [calls get_weather]
The weather in Tokyo is currently 22°C and sunny.
```

Research:
```
You: Research renewable energy trends
Assistant: [calls research_topic]
Researching renewable energy trends... (Ctrl+C to cancel)
| (spinner cycles for 3–8 seconds)
Based on my research, here are the key trends in renewable energy...
```

## Project structure

```
Eloys/
├── main.py                    # All application logic
├── test_main.py               # 16 unit tests (no extra dependencies)
├── requirements.txt           # anthropic, httpx, python-dotenv
├── .env.example               # API key template
├── DISCOVERY.md               # API surprises and handling notes
├── README.md
└── ai-session-transcript.md   # Full build log with decisions and final code
```

## Session transcript

[ai-session-transcript.md](ai-session-transcript.md) documents the complete build session — every feature added, every bug fixed, and the rationale behind non-obvious decisions (history rollback strategy, task cancellation, TTL cache, tool result serialisation).
