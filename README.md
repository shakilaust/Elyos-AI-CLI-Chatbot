# Eloys CLI Chatbot

A Python CLI chatbot powered by Claude with tool-use support for weather lookups and topic research via an external API.

## Requirements

- Python 3.11+
- An Anthropic API key

## Setup

```bash
# 1. Clone / enter the project directory
cd Eloys

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your API key
cp .env.example .env
# Open .env and replace the placeholder with your real key:
#   ANTHROPIC_API_KEY=sk-ant-...
```

## Run

```bash
python3 main.py
```

Type `quit`, `exit`, or `q` to stop. Press `Ctrl+C` at any input prompt to exit cleanly.

## Tools

| Tool | Trigger | Behaviour |
|---|---|---|
| `get_weather` | Questions about current weather | Calls the external weather endpoint; fast, no cancel UI |
| `research_topic` | Research / deep-dive requests | Shows a live spinner; press `Ctrl+C` to cancel mid-request |

Research results are cached in memory for 5 minutes — a repeated query returns instantly.

## Sample interactions

```
You: What's the weather in Tokyo?
Assistant: [calls get_weather]
The weather in Tokyo is currently 22°C and sunny.

You: Research renewable energy trends
Assistant: [calls research_topic]
Researching renewable energy trends... (Ctrl+C to cancel)
| (spinner cycles for 3–8 seconds)
Based on my research, here are the key trends in renewable energy...

You: Research quantum computing
Assistant: [calls research_topic]
Researching quantum computing... (Ctrl+C to cancel)
/ (user presses Ctrl+C after 2 seconds)

Research cancelled.

You:
```

## Project structure

```
Eloys/
├── main.py          # All application logic (~247 lines)
├── requirements.txt # anthropic, httpx, python-dotenv
├── .env.example     # API key template
└── README.md
```
