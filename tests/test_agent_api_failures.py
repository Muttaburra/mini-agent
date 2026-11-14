"""Exercise the real script with mocked SDK and tool boundaries."""

import contextlib
import io
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_llm_client import api_failures, mock_client


SCRIPT = Path(__file__).resolve().parents[1] / "agent_loop.py"


class AgentAPIFailureTests(unittest.TestCase):
    def run_agent(self, client):
        # Exercise the CLI entry point with an offline client.
        # No real client, .env loading, or filesystem tool can run here.
        with patch("openai.OpenAI", return_value=client) as constructor, \
             patch("llm_client.time.sleep"), \
             patch("dotenv.load_dotenv"), \
             patch("logging.basicConfig"), \
             patch("tool_dispatcher.dispatch_tool", return_value=3) as dispatch, \
             contextlib.redirect_stdout(io.StringIO()), \
             self.assertLogs(level="INFO"):
            state = runpy.run_path(str(SCRIPT), run_name="__main__")
            state.update(vars(state["result"]))
        constructor.assert_called_once_with(max_retries=0, timeout=state["LLM_TIMEOUT"])
        self.assertEqual(state["LLM_TIMEOUT"].as_dict(),
                         {"connect": 5.0, "read": 30.0, "write": 10.0, "pool": 5.0})
        return state, dispatch

    def test_initial_api_failure_stops_before_tools(self):
        for error, _, _ in api_failures():
            with self.subTest(error=type(error).__name__):
                client = mock_client()
                client.responses.create.side_effect = error
                state, dispatch = self.run_agent(client)
                self.assertEqual(state["run_status"].value, "api_failed")
                self.assertEqual(state["step"], 0)
                self.assertEqual(state["llm_calls"], 1)
                self.assertEqual(client.responses.create.call_count, 3)
                dispatch.assert_not_called()

    def test_followup_api_failure_stops_after_one_tool(self):
        first_response = SimpleNamespace(
            id="response-1", status="completed",
            output=[SimpleNamespace(type="function_call", name="calculate",
                                    arguments='{"a": 1, "b": 2, "operation": "add"}',
                                    call_id="call-1")],
        )
        for error, _, _ in api_failures():
            with self.subTest(error=type(error).__name__):
                client = mock_client()
                client.responses.create.side_effect = [first_response, error, error, error]
                state, dispatch = self.run_agent(client)
                self.assertEqual(state["run_status"].value, "api_failed")
                self.assertEqual(state["step"], 1)
                self.assertEqual(state["llm_calls"], 2)
                self.assertEqual(client.responses.create.call_count, 4)
                dispatch.assert_called_once_with("calculate", {"a": 1, "b": 2, "operation": "add"})
                followup = client.responses.create.call_args.kwargs
                self.assertEqual(followup["previous_response_id"], "response-1")
                self.assertEqual(followup["input"][0]["call_id"], "call-1")

    def test_followup_recovers_without_repeating_tool(self):
        first = SimpleNamespace(
            id="response-1", status="completed",
            output=[SimpleNamespace(type="function_call", name="calculate",
                                    arguments='{"a": 1, "b": 2, "operation": "add"}',
                                    call_id="call-1")],
        )
        final = SimpleNamespace(status="completed", output=[], output_text="3")
        for error, _, _ in api_failures():
            with self.subTest(error=type(error).__name__):
                client = mock_client()
                client.responses.create.side_effect = [first, error, final]
                state, dispatch = self.run_agent(client)
                self.assertEqual(state["run_status"].value, "completed")
                self.assertEqual(state["llm_calls"], 2)
                self.assertEqual(client.responses.create.call_count, 3)
                dispatch.assert_called_once()
                calls = client.responses.create.call_args_list
                self.assertEqual(calls[1], calls[2])


if __name__ == "__main__":
    unittest.main()
