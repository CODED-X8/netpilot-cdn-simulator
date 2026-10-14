"""Unit tests for Incident Postmortem Generator (Milestone M6).

Tests:
1. Generation of structured postmortem report for a simulated failure event.
2. Verification that all 5 sections (Summary, Timeline, Impact, Root Cause, Mitigations) are present.
3. Verification that all numbers in the postmortem match event store data.
4. Event ID citation grounding verification.
5. Flask REST endpoint POST /api/postmortem/generate.
6. Copilot tool calling agent integration with generate_postmortem.
"""

import uuid
import pytest
from flask import Flask

import services.network_service as net_service
from storage.event_store import get_event_store
from services.postmortem_service import generate_postmortem
from copilot.verifier import verify_number_grounding, verify_event_id_grounding
from copilot.agent import run_copilot_chat
from copilot.llm_provider import FakeLLMProvider
from dashboard.app import app


@pytest.fixture
def simulated_failure_event():
    """Simulate a network link failure to create event telemetry."""
    session = "test_pm_session"
    net_service.reset_network(session_id=session)
    # Simulate what-if failure
    res = net_service.what_if(
        remove_edges=["user_1<->edge_1"],
        source="user_1",
        session_id=session,
    )
    # Also log an actual kill_edge event
    es = get_event_store()
    ev = es.log_event(
        event_type="kill_edge",
        session_id=session,
        topology_name="Sample Hierarchical CDN",
        inputs={"killed_edge": "user_1<->edge_1"},
        results={
            "killed_edge": {"u": "user_1", "v": "edge_1", "latency": 14.0},
            "remaining_edges": 79,
            "before": {"latency": 14.0, "hops": 1},
            "after": {"latency": 28.0, "hops": 2},
            "latency_delta_ms": 14.0,
        },
        event_id=f"evt_pm_test_{uuid.uuid4().hex[:8]}",
    )
    return ev


def test_postmortem_sections_and_content(simulated_failure_event):
    """Verify generated postmortem contains all 5 required structural sections."""
    ev = simulated_failure_event
    pm = generate_postmortem(event_id=ev.id, session_id=ev.session_id)

    assert pm["status"] == "success"
    assert pm["event_id"] == ev.id
    md = pm["markdown"]

    # Check 5 required sections
    assert "## Summary" in md
    assert "## Chronological Timeline" in md
    assert "## Impact Assessment" in md
    assert "## Root Cause Analysis" in md
    assert "## Preventative Mitigations" in md

    # Check target details
    assert "user_1<->edge_1" in md
    assert "Sample Hierarchical CDN" in md


def test_postmortem_number_and_event_grounding(simulated_failure_event):
    """Verify every number and event ID cited in the postmortem matches event store records."""
    ev = simulated_failure_event
    pm = generate_postmortem(event_id=ev.id, session_id=ev.session_id)
    md = pm["markdown"]

    # Number grounding check
    is_grounded, ungrounded, _ = verify_number_grounding(md, [ev.results, ev.inputs, pm["event_data"]])
    assert is_grounded is True
    assert ungrounded == []

    # Event ID grounding check
    ev_ok, invalid_ids, _ = verify_event_id_grounding(md)
    assert ev_ok is True
    assert invalid_ids == []


def test_postmortem_api_endpoint(simulated_failure_event):
    """Verify POST /api/postmortem/generate returns valid report."""
    client = app.test_client()
    ev = simulated_failure_event

    resp = client.post("/api/postmortem/generate", json={"event_id": ev.id})
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["status"] == "success"
    assert data["event_id"] == ev.id
    assert "## Summary" in data["markdown"]


def test_copilot_agent_generates_postmortem():
    """Verify Copilot agent can call generate_postmortem tool."""
    fake_provider = FakeLLMProvider()
    resp = run_copilot_chat(
        message="Please generate a postmortem report for the latest outage",
        session_id="test_pm_agent_session",
        custom_provider=fake_provider,
    )

    assert resp["grounding_verified"] is True
    assert any(t["tool"] == "generate_postmortem" for t in resp["tools_used"])
    assert "postmortem" in resp["answer"].lower()
