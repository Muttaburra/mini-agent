import importlib
import json
import logging
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import httpx2
import pytest
from openai import AuthenticationError, InternalServerError

import agent_loop as agent
from test_llm_client import api_failures, mock_client


def response(*calls, id="resp-1", text="done", status="completed"):
    return NS(id=id, status=status, output=list(calls), output_text=text)


def tool(name="calculate", args=None, call_id="call-1"):
    if args is None:
        args = {"a": 1, "b": 2, "operation": "add"}
    return NS(type="function_call", name=name, arguments=json.dumps(args), call_id=call_id)


def client_for(*events):
    client = mock_client()
    client.responses.create.side_effect = list(events)
    return client


def test_import_is_inert():
    with patch("openai.OpenAI") as constructor, patch("dotenv.load_dotenv") as env:
        importlib.reload(agent)
    constructor.assert_not_called()
    env.assert_not_called()


def test_direct_final_and_independent_runs():
    client = client_for(response(text="42"), response(text="again"))
    first = agent.run_agent(client)
    second = agent.run_agent(client)
    assert first.run_status == agent.RunStatus.COMPLETED
    assert first.final_answer == "42"
    assert first.step == first.llm_calls == second.step == second.llm_calls == 1
    assert first.tool_errors == second.tool_errors == 0


def test_multi_round_protocol():
    client = client_for(response(tool(), id="r1"),
                        response(tool(call_id="c2"), tool(call_id="c3"), id="r2"),
                        response(text="3"))
    result = agent.run_agent(client)
    assert result.run_status == agent.RunStatus.COMPLETED
    assert result.step == result.llm_calls == 3
    calls = client.responses.create.call_args_list
    assert "previous_response_id" not in calls[0].kwargs
    assert calls[0].kwargs["tool_choice"] == "required"
    for index, prior, ids in [(1, "r1", ["call-1"]), (2, "r2", ["c2", "c3"])]:
        kwargs = calls[index].kwargs
        assert kwargs["previous_response_id"] == prior
        assert kwargs["tool_choice"] == "auto"
        assert [item["call_id"] for item in kwargs["input"]] == ids
        assert all(item["type"] == "function_call_output" for item in kwargs["input"])
        assert all(json.loads(item["output"]) == {"ok": True, "result": 3} for item in kwargs["input"])


@pytest.mark.parametrize("arguments,error", [("{", "JSONDecodeError"), ("[]", "ValueError"), ("null", "ValueError"), (None, "TypeError")])
def test_bad_arguments_return_error(arguments, error, caplog):
    call = tool()
    call.arguments = arguments
    client = client_for(response(call), response())
    with caplog.at_level(logging.WARNING):
        result = agent.run_agent(client)
    payload = json.loads(client.responses.create.call_args.kwargs["input"][0]["output"])
    assert payload["ok"] is False
    assert payload["error"]["type"] == error
    assert payload["error"]["message"]
    assert result.tool_errors == 1
    assert "Tool failed" in caplog.text


@pytest.mark.parametrize("error", [ValueError("bad tool"), OSError("disk error"), RuntimeError("unexpected tool error")])
def test_tool_failure_is_not_business_success(error):
    client = client_for(response(tool()), response(text="Could not finish"))
    with patch("agent_loop.dispatch_tool", side_effect=error):
        result = agent.run_agent(client)
    payload = json.loads(client.responses.create.call_args.kwargs["input"][0]["output"])
    assert payload == {"ok": False, "error": {"type": type(error).__name__, "message": str(error)}}
    assert result.run_status == agent.RunStatus.COMPLETED  # Dialogue finished only.
    assert result.tool_errors == 1


@pytest.mark.parametrize("limit", [1, 2, 3])
def test_step_limit(limit):
    client = client_for(*(response(tool(), id=f"r{i}") for i in range(limit)))
    with patch("agent_loop.dispatch_tool", return_value=3) as dispatch:
        result = agent.run_agent(client, max_steps=limit)
    assert result.run_status == agent.RunStatus.MAX_STEPS_EXCEEDED
    assert result.step == result.llm_calls == client.responses.create.call_count == limit
    assert dispatch.call_count == limit - 1


def test_final_answer_on_last_round():
    client = client_for(response(tool()), response(text="3"))
    assert agent.run_agent(client, max_steps=2).run_status == agent.RunStatus.COMPLETED


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_invalid_limit_before_api(limit):
    client = mock_client()
    with pytest.raises(ValueError):
        agent.run_agent(client, max_steps=limit)
    client.responses.create.assert_not_called()


@pytest.mark.parametrize("bad", [NS(), NS(status="completed"), response(status="incomplete"),
    response(text=""), response(text="  "), response(NS()), response(tool(), id=None),
    response(tool(call_id=None)), response(tool(), tool()), response(tool(name=None))])
def test_incomplete_response_stops_before_tools(bad, caplog):
    client = client_for(bad)
    with patch("agent_loop.dispatch_tool") as dispatch, caplog.at_level(logging.WARNING):
        result = agent.run_agent(client)
    assert result.run_status == agent.RunStatus.MODEL_INCOMPLETE
    assert client.responses.create.call_count == 1
    dispatch.assert_not_called()
    assert "Model response" in caplog.text


def failures():
    request = httpx2.Request("POST", "https://example.invalid/v1/responses")
    return [entry[0] for entry in api_failures()] + [
        InternalServerError("injected", response=httpx2.Response(500, request=request), body=None),
        AuthenticationError("injected", response=httpx2.Response(401, request=request), body=None),
    ]


@pytest.mark.parametrize("error", failures(), ids=lambda error: type(error).__name__)
@pytest.mark.parametrize("followup", [False, True])
def test_api_failure_stops_runtime(error, followup, caplog):
    client = client_for(*([response(tool())] if followup else []), error)
    with patch("agent_loop.dispatch_tool", return_value=3) as dispatch, caplog.at_level(logging.INFO):
        result = agent.run_agent(client, max_attempts=1)
    assert result.run_status == agent.RunStatus.API_FAILED
    assert dispatch.call_count == int(followup)
    assert client.responses.create.call_count == result.llm_calls == 1 + int(followup)
    assert "LLM API" in caplog.text and "success=False" in caplog.text


def test_report_to_summary_with_real_tools(workspace):
    (workspace / "report.txt").write_text("100\n200\n50", encoding="utf-8")
    client = client_for(
        response(tool("read_file", {"path": "report.txt"}), id="read"),
        response(tool(args={"a": 100, "b": 200, "operation": "add"}), id="sum1"),
        response(tool(args={"a": 300, "b": 50, "operation": "add"}), id="sum2"),
        response(tool("write_file", {"path": "summary.txt", "content": "350"}), id="write"),
        response(text="总额 350，已写入 summary.txt"),
    )
    result = agent.run_agent(client)
    assert result.run_status == agent.RunStatus.COMPLETED
    assert result.tool_errors == 0
    assert result.llm_calls == 5
    assert (workspace / "summary.txt").read_text(encoding="utf-8") == "350"
    assert (workspace / "report.txt").read_text(encoding="utf-8") == "100\n200\n50"
    values = [json.loads(c.kwargs["input"][0]["output"])["result"]
              for c in client.responses.create.call_args_list[1:]]
    assert values[:3] == ["100\n200\n50", 300, 350]
