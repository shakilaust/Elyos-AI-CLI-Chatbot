# Discovery Notes

## 1. Weather API requires `X-API-Key`

### Behaviour

The API documentation says both endpoints require `X-API-Key`. I confirmed that the weather endpoint rejects requests without it.

Query:

```bash
curl -i "https://elyos-interview-907656039105.europe-west2.run.app/weather?location=London"
```

Response:

```http
HTTP/2 401
```

```json
{"error":"Invalid or missing API key"}
```

### How I discovered it

I intentionally called the weather endpoint without the header to check what failure mode the API used.

### How I handled it in code

`get_weather()` always sends the API key header. If the API still returns an HTTP error, the code catches `httpx.HTTPStatusError`, parses the JSON error body when possible, and returns a structured error dictionary instead of crashing the CLI.

## 2. Weather API predicts or resolves strange locations

### Behaviour

The weather API does not only return weather for normal city names. It sometimes resolves fake, special, or invalid-looking user input into a real-looking location and returns HTTP `200`.

I saw this directly in the CLI:

```text
You: weather of atlantis
Assistant: The current weather in Atlantis is:
- Temperature: 11.3°C
- Condition: Clear
- Humidity: 87%
```

```text
You: weather of null
Assistant: The current weather in Nulles is:
- Temperature: 22.3°C
- Condition: Clear
- Humidity: 57%
```

```text
You: weather of None
Assistant: The current weather in Nonette is:
- Temperature: 16.9°C
- Condition: Clear
- Humidity: 67%
```

```text
You: weather of 12a
Assistant: The current weather in Alexandria is:
- Temperature: 23.3°C
- Condition: Partly cloudy
- Humidity: 83%
```

The most surprising example was `12a`. It is not a location a user would normally expect to be valid, but the API resolved it to `Alexandria`.

Equivalent direct API query:

```bash
curl -i \
  -H "X-API-Key: $ELYOS_API_KEY" \
  "https://elyos-interview-907656039105.europe-west2.run.app/weather?location=12a"
```

Observed response:

```json
{"location":"Alexandria","temperature_c":23.3,"condition":"Partly cloudy","humidity":83}
```

### How I discovered it

I tested the CLI with unusual weather prompts after the normal happy path worked:

- `weather of atlantis`
- `weather of null`
- `weather of None`
- `weather of 12a`

This showed that the LLM was correctly choosing the weather tool, and the API was doing its own location resolution behind the scenes.

### How I handled it in code

I chose not to add client-side location validation.

Reasoning:

- The API clearly has its own location resolution behaviour.
- Local validation could incorrectly reject inputs the API can resolve.
- The assignment asks for graceful API handling, not perfect location correctness.

The code therefore:

- Passes successful weather responses through to the LLM.
- Parses JSON error responses when the API rejects a location.
- Lets the assistant explain the location returned by the API.

The trade-off is that the assistant may present a surprising resolved location, such as `12a` becoming `Alexandria`. With more time, I would make the assistant explicitly say something like: "The weather API resolved `12a` to Alexandria."

## 3. Location-only prompts can be routed to weather

### Behaviour

If the conversation has recently been about weather, a short location-only message can be interpreted as the missing weather location.

Example from the CLI:

```text
You: What is weather today?
Assistant: I'd be happy to help you check the weather! However, I need to know which location you'd like the weather for.

You: Goodmayes
Assistant: Here's the weather for Goodmayes today:
- Temperature: 21.3°C
- Condition: Clear
- Humidity: 73%
```

This is useful when the user is answering the assistant's follow-up question. However, it also creates an ambiguity: if a user simply types a place name like `London`, the model may call the weather tool and return London weather, even though the user might have meant something else, such as London events, travel information, or general research about London.

### How I discovered it

I tested a normal weather conversation where the assistant asked for a missing location, then I replied with only the location name. The app correctly continued the weather flow, but it showed the broader ambiguity around single-word location prompts.

### How I handled it in code

I left the behaviour to the LLM and conversation history rather than hard-coding a rule.

Reasoning:

- In a weather follow-up flow, `London` or `Goodmayes` probably should mean "use this as the weather location."
- Outside that flow, `London` alone is ambiguous and could mean weather, events, travel, history, or research.
- Hard-coding all bare place names as weather would be too aggressive.
- Hard-coding all bare place names as research would break the natural follow-up weather case.

The current implementation preserves conversation history and lets the model infer the user's intent from context.

With more time, I would improve the system prompt/tool descriptions so that the assistant asks a clarifying question for ambiguous standalone locations unless the previous assistant message explicitly asked for a weather location. For example: "Do you want the weather in London, events in London, or general information about London?"
