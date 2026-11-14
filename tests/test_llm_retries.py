"""Bounded retries: fake SDK failures and fake sleep, real wrapper logic."""

import unittest
from unittest.mock import call, patch

import httpx2
from openai import APIError, APIStatusError, AuthenticationError

from llm_client import request_llm
from test_llm_client import api_failures, mock_client


class RetryTests(unittest.TestCase):
    def test_transient_failure_then_success(self):
        for error, _, _ in api_failures():
            with self.subTest(error=type(error).__name__):
                client = mock_client()
                expected = object()
                client.responses.create.side_effect = [error, expected]
                with patch("llm_client.time.sleep") as sleep, \
                     patch("llm_client.time.perf_counter", side_effect=[10.0, 11.25]), \
                     self.assertLogs("llm_client", level="INFO") as logs:
                    response, duration = request_llm(client, max_attempts=3, model="test")
                self.assertIs(response, expected)
                self.assertEqual(duration, 1250.0)
                self.assertEqual(client.responses.create.call_args_list,
                                 [call(model="test"), call(model="test")])
                sleep.assert_called_once_with(1.0)
                self.assertIn("next_attempt=2/3 delay_seconds=1.0", logs.output[1])
                self.assertIn("success=True", logs.output[-1])

    def test_exhaustion_waits_only_between_attempts(self):
        for error, _, _ in api_failures():
            with self.subTest(error=type(error).__name__):
                client = mock_client()
                client.responses.create.side_effect = error
                with patch("llm_client.time.sleep") as sleep, \
                     self.assertLogs("llm_client", level="INFO") as logs:
                    response, _ = request_llm(client, max_attempts=3)
                self.assertIsNone(response)
                self.assertEqual(client.responses.create.call_count, 3)
                self.assertEqual(sleep.call_args_list, [call(1.0), call(2.0)])
                self.assertIn("success=False", logs.output[-1])

    def test_backoff_is_capped(self):
        client = mock_client()
        client.responses.create.side_effect = api_failures()[0][0]
        with patch("llm_client.time.sleep") as sleep, self.assertLogs("llm_client"):
            request_llm(client, max_attempts=6)
        self.assertEqual(client.responses.create.call_count, 6)
        self.assertEqual(sleep.call_args_list,
                         [call(1.0), call(2.0), call(4.0), call(8.0), call(8.0)])

    def test_non_retryable_errors_stop_immediately(self):
        request = httpx2.Request("POST", "https://example.invalid/v1/responses")
        errors = [
            AuthenticationError("invalid key", response=httpx2.Response(401, request=request), body=None),
            APIStatusError("bad request", response=httpx2.Response(400, request=request), body=None),
            APIError("other API error", request, body=None),
        ]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                client = mock_client()
                client.responses.create.side_effect = error
                with patch("llm_client.time.sleep") as sleep, self.assertLogs("llm_client"):
                    response, _ = request_llm(client, max_attempts=3)
                self.assertIsNone(response)
                client.responses.create.assert_called_once()
                sleep.assert_not_called()

    def test_success_does_not_wait_or_retry(self):
        client = mock_client()
        with patch("llm_client.time.sleep") as sleep:
            response, _ = request_llm(client, max_attempts=3)
        self.assertIs(response, client.responses.create.return_value)
        client.responses.create.assert_called_once()
        sleep.assert_not_called()

    def test_programming_error_is_not_retried(self):
        client = mock_client()
        client.responses.create.side_effect = TypeError("invalid argument")
        with patch("llm_client.time.sleep") as sleep:
            with self.assertRaises(TypeError):
                request_llm(client, max_attempts=3)
        client.responses.create.assert_called_once()
        sleep.assert_not_called()

    def test_invalid_attempt_limit_fails_before_api_call(self):
        for value in [0, -1, True, 1.5, "3", None]:
            with self.subTest(value=value):
                client = mock_client()
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    request_llm(client, max_attempts=value)
                client.responses.create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
