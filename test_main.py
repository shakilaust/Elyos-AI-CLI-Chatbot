import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

import main
from main import CACHE_TTL, TOOLS, get_weather, research_topic


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message="error", request=MagicMock(), response=resp
        )
    return resp


def _patch_httpx(response: MagicMock):
    """Return a patch context manager that replaces httpx.AsyncClient."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=response)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return patch("httpx.AsyncClient", return_value=cm)


def _patch_httpx_exc(exc: Exception):
    """Return a patch context manager whose .get() raises exc."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=exc)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return patch("httpx.AsyncClient", return_value=cm)


# ---------------------------------------------------------------------------
# get_weather
# ---------------------------------------------------------------------------

class TestGetWeather(unittest.IsolatedAsyncioTestCase):

    async def test_success_returns_api_data(self):
        data = {"temperature": 22, "condition": "sunny", "city": "Tokyo"}
        with _patch_httpx(_make_response(data)):
            result = await get_weather("Tokyo")
        self.assertEqual(result, data)

    async def test_timeout_returns_error_dict(self):
        with _patch_httpx_exc(httpx.TimeoutException("timed out")):
            result = await get_weather("Tokyo")
        self.assertIn("error", result)
        self.assertIn("timed out", result["error"].lower())
        self.assertEqual(result["location"], "Tokyo")

    async def test_http_error_includes_status_code(self):
        with _patch_httpx(_make_response({}, 503)):
            result = await get_weather("London")
        self.assertIn("error", result)
        self.assertIn("503", result["error"])
        self.assertEqual(result["location"], "London")

    async def test_generic_exception_returns_error_dict(self):
        with _patch_httpx_exc(Exception("connection refused")):
            result = await get_weather("Paris")
        self.assertIn("error", result)
        self.assertEqual(result["location"], "Paris")


# ---------------------------------------------------------------------------
# research_topic
# ---------------------------------------------------------------------------

class TestResearchTopic(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        main._research_cache.clear()

    async def test_success_returns_api_data(self):
        data = {"summary": "Solar panels are booming.", "topic": "solar energy"}
        with _patch_httpx(_make_response(data)):
            result = await research_topic("solar energy")
        self.assertEqual(result, data)

    async def test_cache_hit_skips_http_call(self):
        data = {"summary": "Cached result"}
        main._research_cache["solar energy"] = (data, time.monotonic())
        with patch("httpx.AsyncClient") as mock_cls:
            result = await research_topic("Solar Energy")  # casing difference
        mock_cls.assert_not_called()
        self.assertEqual(result, data)

    async def test_expired_cache_makes_new_request(self):
        stale = {"summary": "Old result"}
        fresh = {"summary": "Fresh result"}
        main._research_cache["wind power"] = (stale, time.monotonic() - CACHE_TTL - 1)
        with _patch_httpx(_make_response(fresh)):
            result = await research_topic("wind power")
        self.assertEqual(result, fresh)

    async def test_successful_result_is_cached(self):
        data = {"summary": "Quantum bits"}
        with _patch_httpx(_make_response(data)):
            await research_topic("quantum computing")
        self.assertIn("quantum computing", main._research_cache)
        cached, _ = main._research_cache["quantum computing"]
        self.assertEqual(cached, data)

    async def test_timeout_returns_error_dict(self):
        with _patch_httpx_exc(httpx.TimeoutException("timed out")):
            result = await research_topic("quantum computing")
        self.assertIn("error", result)
        self.assertIn("timed out", result["error"].lower())
        self.assertEqual(result["topic"], "quantum computing")

    async def test_http_error_includes_status_code(self):
        with _patch_httpx(_make_response({}, 429)):
            result = await research_topic("AI safety")
        self.assertIn("error", result)
        self.assertIn("429", result["error"])
        self.assertEqual(result["topic"], "AI safety")

    async def test_throttled_200_returns_error_and_is_not_cached(self):
        data = {
            "status": "throttled",
            "message": "Rate limit exceeded. Please wait.",
            "retry_after_seconds": 2,
            "data": None,
        }
        with _patch_httpx(_make_response(data)):
            result = await research_topic("solar energy")
        self.assertEqual(result["error"], "Rate limit exceeded. Please wait.")
        self.assertEqual(result["retry_after_seconds"], 2)
        self.assertEqual(result["topic"], "solar energy")
        self.assertNotIn("solar energy", main._research_cache)

    async def test_error_result_is_not_cached(self):
        with _patch_httpx_exc(httpx.TimeoutException("timed out")):
            await research_topic("fusion energy")
        self.assertNotIn("fusion energy", main._research_cache)


# ---------------------------------------------------------------------------
# TOOLS schema
# ---------------------------------------------------------------------------

class TestToolsSchema(unittest.TestCase):

    def test_exactly_two_tools_defined(self):
        self.assertEqual(len(TOOLS), 2)

    def test_get_weather_schema(self):
        tool = next(t for t in TOOLS if t["name"] == "get_weather")
        schema = tool["input_schema"]
        self.assertIn("location", schema["properties"])
        self.assertIn("location", schema["required"])

    def test_research_topic_schema(self):
        tool = next(t for t in TOOLS if t["name"] == "research_topic")
        schema = tool["input_schema"]
        self.assertIn("topic", schema["properties"])
        self.assertIn("topic", schema["required"])

    def test_all_tools_have_descriptions(self):
        for tool in TOOLS:
            self.assertIn("description", tool, f"{tool['name']} missing description")
            self.assertTrue(tool["description"].strip(), f"{tool['name']} description is empty")


if __name__ == "__main__":
    unittest.main(verbosity=2)
