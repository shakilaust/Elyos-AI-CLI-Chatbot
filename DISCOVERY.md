# Discovery Notes

These notes cover the unexpected API behaviours found while probing the supplied Elyos endpoints and while wiring the tool calls into Claude.

## Weather API

### Missing API key returns JSON `401`

- **Behaviour:** Calling `/weather?location=London` without `X-API-Key` returned `401` with `{"error":"Invalid or missing API key"}`.
- **How discovered:** Manual `curl` probe without the auth header.
- **Code handling:** `get_weather()` catches `httpx.HTTPStatusError`, attempts to parse the response JSON, and returns a structured error dict instead of raising.

### Missing `location` returns FastAPI-style `422`

- **Behaviour:** Calling `/weather` without a `location` query parameter returned `422` with a `detail` validation payload.
- **How discovered:** Manual `curl` probe omitting the query parameter.
- **Code handling:** The wrapper catches non-2xx statuses and returns an error dict to the LLM so the chat loop can continue.

### Empty `location` returns `404`, but unknown locations can return `200`

- **Behaviour:** `/weather?location=` returned `404` with `{"error":"Location \"\" not found"}`. However, `/weather?location=Atlantis` returned a plausible weather payload with HTTP `200`.
- **How discovered:** Manual `curl` probes against empty and obviously fake locations.
- **Code handling:** The code does not try to validate whether a city is real. It passes successful weather payloads through, but parses JSON error bodies on HTTP failures so the assistant can explain failures cleanly.

## Research API

### Research is slow by design

- **Behaviour:** A normal research request took about 6.5 seconds in manual testing.
- **How discovered:** Timed `curl` probe against `/research?topic=solar+energy`.
- **Code handling:** `research_topic()` is run inside an `asyncio.Task`, and the CLI shows a spinner with `Researching {topic}... (Ctrl+C to cancel)` while the API call is pending.

### Missing `topic` returns FastAPI-style `422`

- **Behaviour:** Calling `/research` without a `topic` query parameter returned `422` with a validation payload.
- **How discovered:** Manual `curl` probe omitting the query parameter.
- **Code handling:** The wrapper catches the HTTP error and returns a structured error dict instead of crashing the chat loop.

### Rate limiting returns HTTP `200`

- **Behaviour:** After several research calls, the API returned HTTP `200` with `{"status":"throttled","message":"Rate limit exceeded. Please wait.","retry_after_seconds":2,"data":null}` instead of using HTTP `429`.
- **How discovered:** Manual repeated `curl` probes to `/research`.
- **Code handling:** `_api_error_payload()` detects `status == "throttled"` even on successful HTTP responses, converts it to an error dict, preserves `retry_after_seconds`, and avoids caching the throttled response.

## Anthropic SDK/tool-use surprises

### `get_final_message()` must be awaited

- **Behaviour:** `stream.get_final_message()` returns a coroutine. Forgetting `await` caused an attribute error when reading `stop_reason`.
- **How discovered:** Runtime error during development.
- **Code handling:** The stream final message is awaited before checking `stop_reason` and reading `tool_use` blocks.

### Tool result content must be a string

- **Behaviour:** Claude tool result content should be sent as string content, not a raw Python dict.
- **How discovered:** Anthropic tool-use integration while wiring the second model call.
- **Code handling:** Tool outputs are serialized with `json.dumps(result)` before being appended as `tool_result` content.

### Cancelled tool turns can corrupt conversation history

- **Behaviour:** If a research call is cancelled after the user message is added but before tool results are appended, the next turn can leave consecutive user messages or dangling tool-use state.
- **How discovered:** Manual review of all conversation-history paths during cancellation hardening.
- **Code handling:** Mid-tool cancellation pops the current user turn. Mid-second-stream cancellation rolls back the user input, assistant tool-use message, and user tool-results message.
