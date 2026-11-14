"""Step 3C: deterministic API failures, without credentials or network calls."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx2
from openai import APITimeoutError, APIConnectionError, RateLimitError

from llm_client import request_llm


def api_failures():
    request = httpx2.Request("POST", "https://example.invalid/v1/responses")
    return (
        (APITimeoutError(request), "ERROR", "LLM API timeout"),
        (APIConnectionError(request=request), "ERROR", "LLM API connection failed"),
        (RateLimitError(
            "Too many requests",
            response=httpx2.Response(429, request=request),
            body={"error": {"code": "rate_limit_exceeded"}},
        ), "WARNING", "LLM API rate limit exceeded"),
    )


def mock_client():
    # Only the SDK boundary is replaced; request_llm runs its real code.
    return SimpleNamespace(responses=SimpleNamespace(create=Mock()), close=Mock())


class RequestLLMTests(unittest.TestCase):
    def test_api_failures_return_none_and_log_category_and_duration(self):
        for error, level, message in api_failures():
            with self.subTest(error=type(error).__name__):
                client = mock_client()
                client.responses.create.side_effect = error
                with patch("llm_client.time.perf_counter", side_effect=[10.0, 10.125]):
                    with self.assertLogs("llm_client", level="INFO") as logs:
                        response, duration_ms = request_llm(client, model="test-model", input="hello")

                self.assertIsNone(response)
                self.assertEqual(duration_ms, 125.0)
                self.assertEqual(logs.output, [
                    f"{level}:llm_client:{message}",
                    "INFO:llm_client:LLM request finished: success=False duration_ms=125.00",
                ])
                client.responses.create.assert_called_once_with(model="test-model", input="hello")

    def test_success_preserves_response_and_forwards_all_arguments(self):
        client = mock_client()
        expected = object()
        client.responses.create.return_value = expected
        kwargs = dict(model="test-model", input=[], tools=[], tool_choice="auto",
                      previous_response_id="previous", parallel_tool_calls=False)
        with patch("llm_client.time.perf_counter", side_effect=[20.0, 20.25]):
            with self.assertLogs("llm_client", level="INFO") as logs:
                response, duration_ms = request_llm(client, **kwargs)
        self.assertIs(response, expected)
        self.assertEqual(duration_ms, 250.0)
        client.responses.create.assert_called_once_with(**kwargs)
        self.assertIn("success=True duration_ms=250.00", logs.output[0])

    def test_programming_error_is_not_swallowed(self):
        client = mock_client()
        client.responses.create.side_effect = TypeError("invalid argument")
        with self.assertRaisesRegex(TypeError, "invalid argument"):
            request_llm(client, model="test-model")


if __name__ == "__main__":
    unittest.main()
