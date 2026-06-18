import asyncio
import json
import os
import time

import anthropic
import httpx
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-haiku-4-5"
BASE_URL = "https://elyos-interview-907656039105.europe-west2.run.app"
API_KEY_HEADER = {"X-API-Key": "elyos2025"}
CACHE_TTL = 300  # seconds

_research_cache: dict[str, tuple[dict, float]] = {}

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get current weather for a location.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name or location to get weather for.",
                }
            },
            "required": ["location"],
        },
    },
    {
        "name": "research_topic",
        "description": "Research a topic and return relevant information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The topic to research.",
                }
            },
            "required": ["topic"],
        },
    },
]


def _api_error_payload(payload: object, context_key: str, context_value: str) -> dict | None:
    if not isinstance(payload, dict):
        return None

    if payload.get("status") == "throttled":
        return {
            "error": payload.get("message", "API request throttled"),
            "retry_after_seconds": payload.get("retry_after_seconds"),
            context_key: context_value,
        }

    if "error" in payload:
        return {"error": str(payload["error"]), context_key: context_value}

    return None


def _http_error_payload(e: httpx.HTTPStatusError, context_key: str, context_value: str) -> dict:
    try:
        payload = e.response.json()
    except Exception:
        payload = None

    api_error = _api_error_payload(payload, context_key, context_value)
    if api_error:
        api_error["status_code"] = e.response.status_code
        return api_error

    return {"error": f"HTTP {e.response.status_code}", context_key: context_value}


async def get_weather(location: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{BASE_URL}/weather",
                headers=API_KEY_HEADER,
                params={"location": location},
            )
            resp.raise_for_status()
            result = resp.json()
            return _api_error_payload(result, "location", location) or result
    except httpx.TimeoutException:
        return {"error": "Request timed out", "location": location}
    except httpx.HTTPStatusError as e:
        return _http_error_payload(e, "location", location)
    except Exception as e:
        return {"error": str(e), "location": location}


async def research_topic(topic: str) -> dict:
    cache_key = topic.lower().strip()
    cached_result, cached_at = _research_cache.get(cache_key, (None, 0.0))
    if cached_result is not None and time.monotonic() - cached_at < CACHE_TTL:
        return cached_result

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BASE_URL}/research",
                headers=API_KEY_HEADER,
                params={"topic": topic},
            )
            resp.raise_for_status()
            result = resp.json()
            api_error = _api_error_payload(result, "topic", topic)
            if api_error:
                return api_error
    except httpx.TimeoutException:
        return {"error": "Request timed out", "topic": topic}
    except httpx.HTTPStatusError as e:
        return _http_error_payload(e, "topic", topic)
    except Exception as e:
        return {"error": str(e), "topic": topic}

    _research_cache[cache_key] = (result, time.monotonic())
    return result


async def _spinner() -> None:
    frames = ["|", "/", "-", "\\"]
    i = 0
    while True:
        print(f"\r{frames[i % 4]}", end="", flush=True)
        i += 1
        await asyncio.sleep(0.1)


async def main() -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set — copy .env.example to .env and fill it in")

    client = anthropic.AsyncAnthropic(api_key=api_key)
    conversation_history: list[dict] = []

    print("CLI Chatbot — type 'quit', 'exit', or 'q' to stop\n")

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break

            if not user_input:
                continue

            conversation_history.append({"role": "user", "content": user_input})

            print("Assistant: ", end="", flush=True)
            full_response = ""

            async with client.messages.stream(
                model=MODEL,
                max_tokens=8192,
                tools=TOOLS,
                messages=conversation_history,
            ) as stream:
                async for text in stream.text_stream:
                    print(text, end="", flush=True)
                    full_response += text
                # get_final_message() is required to read stop_reason and the full
                # content block list; text_stream alone does not expose these.
                final_message = await stream.get_final_message()

            if final_message.stop_reason == "tool_use":
                if full_response:
                    # Claude occasionally emits a text block before tool_use;
                    # print a newline so the next line starts cleanly.
                    print()

                # History strategy across all cancellation paths:
                # - user_input is always appended before the first stream (above).
                # - tool_use + tool_results are appended only after tools succeed.
                # - mid-tool cancel: pop user_input so the turn leaves no trace.
                # - mid-LLM-stream cancel: pop user_input + assistant_tool_use +
                #   user_tool_results (3 entries) — history must end with an assistant
                #   message or be empty so the next turn's alternating order is valid.
                # - Normal completion: final assistant reply appended at the bottom.
                tool_results = []
                research_cancelled = False

                for block in final_message.content:
                    if block.type != "tool_use":
                        continue

                    if block.name == "get_weather":
                        result = await get_weather(**block.input)

                    elif block.name == "research_topic":
                        topic = block.input.get("topic", "")
                        print(f"Researching {topic}... (Ctrl+C to cancel)")
                        spinner_task = asyncio.create_task(_spinner())
                        # Wrapped in a Task so it can be cancelled independently
                        # without cancelling the parent coroutine.
                        research_task = asyncio.create_task(research_topic(**block.input))
                        try:
                            result = await research_task
                        except (KeyboardInterrupt, asyncio.CancelledError):
                            research_cancelled = True
                        finally:
                            research_task.cancel()
                            try:
                                await research_task
                            except asyncio.CancelledError:
                                pass
                            spinner_task.cancel()
                            try:
                                await spinner_task
                            except asyncio.CancelledError:
                                pass
                            print("\r \r", end="", flush=True)
                        if research_cancelled:
                            print("\nResearch cancelled.")
                            break

                    else:
                        result = {"error": f"Unknown tool: {block.name}"}

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),  # API requires string, not dict
                        }
                    )

                if research_cancelled:
                    conversation_history.pop()  # remove user_input; turn leaves no trace
                    continue

                conversation_history.append(
                    {"role": "assistant", "content": final_message.content}
                )
                conversation_history.append({"role": "user", "content": tool_results})

                full_response = ""
                print("Assistant: ", end="", flush=True)
                try:
                    async with client.messages.stream(
                        model=MODEL,
                        max_tokens=8192,
                        tools=TOOLS,
                        messages=conversation_history,
                    ) as stream:
                        async for text in stream.text_stream:
                            print(text, end="", flush=True)
                            full_response += text
                except (KeyboardInterrupt, asyncio.CancelledError):
                    # Partial text is already on screen; don't append it to history.
                    # Roll back all three entries from this turn so history stays in
                    # valid alternating user/assistant order for the next prompt.
                    for _ in range(3):
                        conversation_history.pop()
                    print()
                    continue

            print()
            conversation_history.append({"role": "assistant", "content": full_response})

    except Exception as e:
        print(f"\nUnexpected error: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
