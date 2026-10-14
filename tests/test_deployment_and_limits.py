"""Unit tests for deployment guardrails: rate limiting, token budget, and kill switch (Milestone M4)."""

import os
import pytest
from flask import Flask

from dashboard.app import app
from copilot.guardrails import (
    reset_guardrails,
    check_rate_limit,
    check_daily_token_budget,
    record_tokens_consumed,
    is_copilot_enabled,
)


@pytest.fixture(autouse=True)
def cleanup_guardrails():
    """Ensure in-memory guardrail counters are clean before each test."""
    reset_guardrails()
    yield
    reset_guardrails()


def test_rate_limiter_blocks_burst(monkeypatch):
    """Test that rate limiter triggers 429 after exceeding RATE_LIMIT_PER_MINUTE."""
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
    session = "session_rate_test"

    # First 3 requests should pass
    for _ in range(3):
        allowed, retry_after = check_rate_limit(session)
        assert allowed is True
        assert retry_after is None

    # 4th request within the minute window must fail
    allowed, retry_after = check_rate_limit(session)
    assert allowed is False
    assert retry_after is not None
    assert retry_after > 0

    # Different session should still be allowed
    allowed_other, _ = check_rate_limit("other_session")
    assert allowed_other is True


def test_daily_token_budget_exhaustion(monkeypatch):
    """Test that token budget tracker flags 429 once threshold is crossed."""
    monkeypatch.setenv("DAILY_TOKEN_BUDGET", "500")

    # Initial check should pass
    ok, used, budget = check_daily_token_budget()
    assert ok is True
    assert used == 0
    assert budget == 500

    # Consume 400 tokens
    record_tokens_consumed(400)
    ok, used, budget = check_daily_token_budget()
    assert ok is True
    assert used == 400

    # Consume another 150 tokens (total 550 >= 500)
    record_tokens_consumed(150)
    ok, used, budget = check_daily_token_budget()
    assert ok is False
    assert used == 550


def test_copilot_kill_switch(monkeypatch):
    """Test that COPILOT_ENABLED=false shuts down chat with 503 while network API remains healthy."""
    client = app.test_client()

    monkeypatch.setenv("COPILOT_ENABLED", "false")
    assert is_copilot_enabled() is False

    # Copilot chat endpoint should return 503
    resp_chat = client.post("/api/copilot/chat", json={"message": "hello"})
    assert resp_chat.status_code == 503
    data = resp_chat.get_json()
    assert "administratively disabled" in data["error"]

    # Main application endpoints must continue functioning normally
    resp_net = client.get("/api/network")
    assert resp_net.status_code == 200
    net_data = resp_net.get_json()
    assert "nodes" in net_data
    assert "edges" in net_data


def test_copilot_chat_rate_limit_endpoint(monkeypatch):
    """Test 429 response on /api/copilot/chat via Flask test client."""
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    monkeypatch.setenv("COPILOT_ENABLED", "true")
    client = app.test_client()

    headers = {"X-Session-ID": "test_burst_session"}

    # 1st request
    r1 = client.post("/api/copilot/chat", json={"message": "what is the bottleneck?"}, headers=headers)
    assert r1.status_code == 200

    # 2nd request
    r2 = client.post("/api/copilot/chat", json={"message": "what is the bottleneck?"}, headers=headers)
    assert r2.status_code == 200

    # 3rd request should trigger 429
    r3 = client.post("/api/copilot/chat", json={"message": "what is the bottleneck?"}, headers=headers)
    assert r3.status_code == 429
    assert "Retry-After" in r3.headers
    assert "Rate limit exceeded" in r3.get_json()["error"]
