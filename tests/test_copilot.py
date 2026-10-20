"""Unit tests for NetPilot AI Copilot (Milestone M3).

Tests:
1. FakeLLMProvider deterministic scripted mappings.
2. Tool execution via execute_tool_call with Pydantic validation.
3. Number grounding verifier (passes when grounded, flags hallucinated numbers).
4. Destructive actions require explicit confirmation.
5. Copilot agent loop integration with FakeLLMProvider.
6. Flask endpoint POST /api/copilot/chat.
"""

import json
import pytest
from flask import Flask

from copilot.llm_provider import FakeLLMProvider, LLMResponse, LLMToolCall
from copilot.tools import execute_tool_call
from copilot.verifier import (
    extract_numbers_from_text,
    extract_numbers_from_tool_results,
    verify_number_grounding,
)
from copilot.agent import run_copilot_chat
from dashboard.app import app


# ---------------------------------------------------------
# 1. FakeLLMProvider Tests
# ---------------------------------------------------------
def test_fake_llm_provider_queries():
    """Verify FakeLLMProvider maps prompt triggers to proper tool calls."""
    provider = FakeLLMProvider()

    # What-if failure query
    res_fail = provider.chat_complete([{"role": "user", "content": "What happens if edge_2 fails?"}])
    assert len(res_fail.tool_calls) == 1
    assert res_fail.tool_calls[0].function_name == "what_if"
    assert "edge_2" in res_fail.tool_calls[0].arguments.get("remove_edges", [""])[0]

    # Bottleneck query
    res_bot = provider.chat_complete([{"role": "user", "content": "Where is the bottleneck in the network?"}])
    assert len(res_bot.tool_calls) == 1
    assert res_bot.tool_calls[0].function_name == "find_bottleneck"

    # Max flow query
    res_flow = provider.chat_complete([{"role": "user", "content": "What is the max flow throughput?"}])
    assert len(res_flow.tool_calls) == 1
    assert res_flow.tool_calls[0].function_name == "max_flow"

    # Default query -> shortest path
    res_path = provider.chat_complete([{"role": "user", "content": "Where should traffic go?"}])
    assert len(res_path.tool_calls) == 1
    assert res_path.tool_calls[0].function_name == "shortest_path"


# ---------------------------------------------------------
# 2. Pydantic Tool Validation Tests
# ---------------------------------------------------------
def test_tool_argument_validation():
    """Verify tool arguments are validated via Pydantic schemas."""
    # Invalid algo for shortest_path
    res, is_conf = execute_tool_call("shortest_path", {"source": "user_1", "algo": "invalid_algo"})
    assert "error" in res
    assert "Invalid arguments" in res["error"]
    assert not is_conf

    # Missing required argument 'source' for shortest_path
    res, is_conf = execute_tool_call("shortest_path", {})
    assert "error" in res
    assert not is_conf

    # Unrecognized tool
    res, is_conf = execute_tool_call("non_existent_tool", {})
    assert "error" in res
    assert not is_conf

    # Valid call to get_metrics
    res, is_conf = execute_tool_call("get_metrics", {})
    assert not is_conf
    assert "node_count" in res
    assert res["node_count"] > 0


# ---------------------------------------------------------
# 3. Destructive Action Confirmation Gate Tests
# ---------------------------------------------------------
def test_destructive_action_confirmation():
    """Ensure destructive operations require confirmation."""
    # kill_edge without confirmed=True
    res, is_conf = execute_tool_call("kill_edge", {"edge_id": "user_1<->edge_1", "confirmed": False})
    assert is_conf is True
    assert res.get("confirmation_required") is True

    # reset_network without confirmed=True
    res, is_conf = execute_tool_call("reset_network", {"confirmed": False})
    assert is_conf is True
    assert res.get("confirmation_required") is True

    # kill_edge with confirmed=True executes
    res, is_conf = execute_tool_call("kill_edge", {"edge_id": "user_1<->edge_1", "confirmed": True})
    assert is_conf is False
    assert res.get("status") == "success"
    assert "killed_edge" in res


# ---------------------------------------------------------
# 4. Number Grounding Verifier Tests
# ---------------------------------------------------------
def test_number_grounding_verifier():
    """Verify number grounding check extracts numbers, verifies ground truth, and flags hallucinations."""
    # Number extraction
    text = "The latency increased by 14.5 ms from 25.0 ms to 39.5 ms with 3 hops."
    nums = extract_numbers_from_text(text)
    assert set(nums) == {14.5, 25.0, 39.5, 3.0}

    # Tool output number harvest
    tool_data = {
        "latency_delta_ms": 14.5,
        "before": {"latency": 25.0, "hops": 2},
        "after": {"latency": 39.5, "hops": 3},
    }
    tool_nums = extract_numbers_from_tool_results(tool_data)
    assert {14.5, 25.0, 39.5, 3.0, 2.0}.issubset(tool_nums)

    # Valid grounded check
    is_grounded, ungrounded, output_text = verify_number_grounding(text, [tool_data])
    assert is_grounded is True
    assert ungrounded == []
    assert output_text == text

    # Hallucinated number check (e.g. 999.9 ms)
    hallucinated_text = "The latency increased by 999.9 ms from 25.0 ms."
    is_grounded, ungrounded, flagged_text = verify_number_grounding(hallucinated_text, [tool_data])
    assert is_grounded is False
    assert 999.9 in ungrounded
    assert "Verification Notice" in flagged_text


# ---------------------------------------------------------
# 5. Agent Loop with FakeLLMProvider
# ---------------------------------------------------------
def test_copilot_agent_loop_what_if():
    """Verify full agent loop runs tool call and synthesizes grounded answer."""
    fake_provider = FakeLLMProvider()
    resp = run_copilot_chat(
        message="What happens if edge_1 fails?",
        session_id="test_copilot_session",
        custom_provider=fake_provider,
    )

    assert resp["grounding_verified"] is True
    assert len(resp["tools_used"]) >= 1
    assert resp["tools_used"][0]["tool"] == "what_if"
    assert "what_if" in resp["answer"]
    assert resp["tokens"] > 0
    assert resp["latency_ms"] >= 0
    assert resp["model_used"] == "fake-llm"
    assert resp["provider_used"] == "fake"


def test_copilot_agent_loop_destructive_confirmation():
    """Verify agent loop halts when a destructive action is requested without confirmation."""
    fake_provider = FakeLLMProvider()
    resp = run_copilot_chat(
        message="Please kill edge user_1<->edge_1",
        session_id="test_copilot_session",
        custom_provider=fake_provider,
    )

    assert resp["requires_confirmation"] is True
    assert resp["confirmation_action"] is not None
    assert resp["confirmation_action"]["tool"] == "kill_edge"
    assert "requires your confirmation" in resp["answer"]

    # Now verify executing with confirm_action works
    confirm_resp = run_copilot_chat(
        message="",
        session_id="test_copilot_session",
        confirm_action={"tool": "kill_edge", "arguments": {"edge_id": "user_1<->edge_1"}, "confirmed": True},
        custom_provider=fake_provider,
    )
    assert confirm_resp["requires_confirmation"] is False
    assert "Action confirmed and executed" in confirm_resp["answer"]


# ---------------------------------------------------------
# 6. Flask Endpoint POST /api/copilot/chat
# ---------------------------------------------------------
def test_copilot_chat_api_endpoint(monkeypatch):
    """Test Flask endpoint /api/copilot/chat."""
    client = app.test_client()

    # When API keys are not set, should return offline/disabled explanation
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    resp = client.post("/api/copilot/chat", json={"message": "What is the bottleneck?"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "disabled" in data["answer"].lower() or "offline" in data["answer"].lower()

    # Empty payload returns 400
    resp_empty = client.post("/api/copilot/chat", json={})
    assert resp_empty.status_code == 400


def test_groq_provider_detection(monkeypatch):
    """Test that GROQ_API_KEY automatically configures Groq endpoint and llama-3.3-70b-versatile."""
    from copilot.llm_provider import get_llm_provider, get_active_provider_name

    monkeypatch.setenv("GROQ_API_KEY", "gsk_testkey123456789")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    assert get_active_provider_name() == "groq"
    provider = get_llm_provider()
    assert provider is not None
    assert provider.base_url == "https://api.groq.com/openai/v1"
    assert provider.model == "openai/gpt-oss-120b"

    # Custom Groq model override
    monkeypatch.setenv("GROQ_MODEL", "llama-3.1-8b-instant")
    provider2 = get_llm_provider()
    assert provider2.model == "llama-3.1-8b-instant"


def test_openai_provider_detection(monkeypatch):
    """Test standard OpenAI provider detection and error handling."""
    import pytest
    from copilot.llm_provider import (
        get_llm_provider,
        get_active_provider_name,
        OpenAICompatibleProvider,
    )

    # 1. Standard OpenAI provider configuration
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "sk-proj-test123456")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert get_active_provider_name() == "openai"

    prov = get_llm_provider()
    assert prov is not None
    assert prov.model == "gpt-4o-mini"
    assert "api.openai.com" in prov.base_url

    # 2. Test error handling when primary API call fails
    failing_primary = OpenAICompatibleProvider(
        api_key="broken_key",
        base_url="https://broken-primary.invalid/v1",
        model="primary-test",
        timeout=1,
    )
    with pytest.raises(RuntimeError) as exc_info:
        failing_primary.chat_complete([{"role": "user", "content": "hi"}])
    assert "LLM API" in str(exc_info.value)

