"""Offline acceptance: real Agent + wrapper + SDK, fake HTTP and tools."""

import contextlib
import io
import json
from pathlib import Path
import runpy
import unittest
from unittest.mock import call, patch

import httpx2
from openai import OpenAI


SCRIPT = Path(__file__).resolve().parents[1] / "agent_loop.py"
TRANSIENT_FAULTS = ("connect_timeout", "read_timeout", "write_timeout",
                    "pool_timeout", "network", 429)


def completed_response(with_tool=False):
    output = [{
        "type": "function_call", "id": "fc_test", "call_id": "call_test",
        "name": "calculate", "arguments": '{"a":1,"b":2,"operation":"add"}',
        "status": "completed",
    }] if with_tool else [{
        "type": "message", "id": "msg_test", "role": "assistant", "status": "completed",
        "content": [{"type": "output_text", "text": "3", "annotations": []}],
    }]
    return {
        "id": "resp_tool" if with_tool else "resp_final", "object": "response",
        "created_at": 0, "model": "test-model", "status": "completed", "output": output,
        "parallel_tool_calls": False, "tool_choice": "auto", "tools": [],
    }


class HTTPFaultInjectionTests(unittest.TestCase):
    def run_scenario(self, events):
        requests = []
        events = list(events)

        def transport_handler(request):
            requests.append(request)
            # An unexpected extra SDK retry will also fail the count assertions.
            if not events:
                raise RuntimeError("Unexpected extra HTTP request")
            event = events.pop(0)
            exceptions = {
                "connect_timeout": httpx2.ConnectTimeout,
                "read_timeout": httpx2.ReadTimeout,
                "write_timeout": httpx2.WriteTimeout,
                "pool_timeout": httpx2.PoolTimeout,
                "network": httpx2.ConnectError,
            }
            if isinstance(event, str):
                raise exceptions[event]("Injected test fault", request=request)
            if isinstance(event, int):
                return httpx2.Response(event, json={"error": {
                    "message": "Injected HTTP failure", "type": "test_error",
                    "code": "rate_limit_exceeded" if event == 429 else "test_error",
                }})
            return httpx2.Response(200, json=event)

        def create_offline_client(**kwargs):
            # Keep production timeout/retry options. Never load real credentials.
            client = OpenAI(
                api_key="offline-test-key", base_url="https://example.invalid/v1",
                http_client=httpx2.Client(transport=httpx2.MockTransport(transport_handler),
                                         trust_env=False),
                **kwargs,
            )
            self.addCleanup(client.close)
            return client

        output = io.StringIO()
        with patch("openai.OpenAI", side_effect=create_offline_client), \
             patch("dotenv.load_dotenv"), patch("logging.basicConfig"), \
             patch("llm_client.time.sleep") as sleep, \
             patch("tool_dispatcher.dispatch_tool", return_value=3) as dispatch, \
             contextlib.redirect_stdout(output), \
             self.assertLogs("llm_client", level="INFO") as logs:
            state = runpy.run_path(str(SCRIPT), run_name="__main__")
            state.update(vars(state["result"]))

        self.assertEqual(events, [], "All injected events should be consumed")
        for request in requests:
            self.assertEqual(request.extensions["timeout"],
                             {"connect": 5.0, "read": 30.0, "write": 10.0, "pool": 5.0})
            self.assertEqual(request.url.path, "/v1/responses")
        return state, requests, sleep, dispatch, logs.output, output.getvalue()

    def assert_fault_logged(self, fault, logs):
        expected = ("LLM API rate limit exceeded" if fault == 429 else
                    "LLM API connection failed" if fault == "network" else "LLM API timeout")
        self.assertTrue(any(expected in line for line in logs), logs)

    def test_initial_fault_recovers(self):
        for fault in TRANSIENT_FAULTS:
            with self.subTest(fault=fault):
                state, requests, sleep, dispatch, logs, output = self.run_scenario(
                    [fault, completed_response()])
                self.assertEqual(state["run_status"].value, "completed")
                self.assertEqual(state["llm_calls"], 1)
                self.assertEqual(len(requests), 2)
                sleep.assert_called_once_with(1.0)
                dispatch.assert_not_called()
                self.assertIn("Final answer: 3", output)
                self.assert_fault_logged(fault, logs)

    def test_initial_fault_exhausts_budget(self):
        for fault in TRANSIENT_FAULTS:
            with self.subTest(fault=fault):
                state, requests, sleep, dispatch, logs, _ = self.run_scenario([fault] * 3)
                self.assertEqual(state["run_status"].value, "api_failed")
                self.assertEqual(state["step"], 0)
                self.assertEqual(len(requests), 3)
                self.assertEqual(sleep.call_args_list, [call(1.0), call(2.0)])
                dispatch.assert_not_called()
                self.assert_fault_logged(fault, logs)

    def test_followup_recovers_without_repeating_tool(self):
        for fault in TRANSIENT_FAULTS:
            with self.subTest(fault=fault):
                state, requests, sleep, dispatch, _, _ = self.run_scenario(
                    [completed_response(with_tool=True), fault, completed_response()])
                self.assertEqual(state["run_status"].value, "completed")
                self.assertEqual(state["llm_calls"], 2)
                self.assertEqual(len(requests), 3)
                sleep.assert_called_once_with(1.0)
                dispatch.assert_called_once_with("calculate", {"a": 1, "b": 2, "operation": "add"})
                self.assertEqual(requests[1].content, requests[2].content)
                body = json.loads(requests[2].content)
                self.assertEqual(body["previous_response_id"], "resp_tool")
                self.assertEqual(body["input"][0]["call_id"], "call_test")
                self.assertEqual(json.loads(body["input"][0]["output"]), {"ok": True, "result": 3})

    def test_followup_exhausts_budget_without_repeating_tool(self):
        for fault in TRANSIENT_FAULTS:
            with self.subTest(fault=fault):
                state, requests, sleep, dispatch, _, _ = self.run_scenario(
                    [completed_response(with_tool=True), fault, fault, fault])
                self.assertEqual(state["run_status"].value, "api_failed")
                self.assertEqual(state["llm_calls"], 2)
                self.assertEqual(len(requests), 4)
                self.assertEqual(sleep.call_args_list, [call(1.0), call(2.0)])
                dispatch.assert_called_once()

    def test_other_http_errors_stop_without_retry(self):
        # Current policy deliberately excludes 5xx retries.
        for status in (400, 401, 500):
            with self.subTest(status=status):
                state, requests, sleep, dispatch, logs, _ = self.run_scenario([status])
                self.assertEqual(state["run_status"].value, "api_failed")
                self.assertEqual(len(requests), 1)
                sleep.assert_not_called()
                dispatch.assert_not_called()
                expected = "authentication failed" if status == 401 else f"status={status}"
                self.assertTrue(any(expected in line for line in logs), logs)


if __name__ == "__main__":
    unittest.main()
