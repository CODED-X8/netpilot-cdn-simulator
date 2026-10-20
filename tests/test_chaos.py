"""Tests for Milestone X3: Chaos Mode Engine, Auto-Reset, and Postmortem Generation.

Verifies:
1. Chaos configuration validation (min interval 5s, max failures >= 1).
2. Chaos tick execution (random link severed, route recomputed, event logged to EventStore, automated postmortem generated).
3. Auto-reset condition triggered after M failures (topology restored, status updated).
4. Manual stop with topology restoration.
5. Multi-session isolation.
6. Flask REST API endpoints (/api/chaos/start, /api/chaos/tick, /api/chaos/stop, /api/chaos/status).
"""

import pytest
from services.chaos_service import (
    start_chaos,
    chaos_tick,
    stop_chaos,
    get_chaos_status,
    reset_chaos_state,
)
import services.network_service as net_service
from storage.event_store import get_event_store
from dashboard.app import app


@pytest.fixture(autouse=True)
def clean_chaos_and_network():
    """Ensure clean chaos and topology state before and after each test."""
    reset_chaos_state()
    net_service.reset_network("test_session")
    net_service.reset_network("session_a")
    net_service.reset_network("session_b")
    yield
    reset_chaos_state()
    net_service.reset_network("test_session")
    net_service.reset_network("session_a")
    net_service.reset_network("session_b")


def test_chaos_config_validation():
    """Verify minimum interval of 5s and minimum failure count of 1 are strictly enforced."""
    session_id = "test_session"

    # N < 5 must raise ValueError
    with pytest.raises(ValueError) as excinfo:
        start_chaos(session_id=session_id, interval_seconds=4, max_failures=5)
    assert "at least 5 seconds" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        start_chaos(session_id=session_id, interval_seconds=0, max_failures=5)
    assert "at least 5 seconds" in str(excinfo.value)

    # M < 1 must raise ValueError
    with pytest.raises(ValueError) as excinfo:
        start_chaos(session_id=session_id, interval_seconds=5, max_failures=0)
    assert "must be at least 1" in str(excinfo.value)

    # Valid config succeeds
    res = start_chaos(session_id=session_id, interval_seconds=5, max_failures=3)
    assert res["status"] == "started"
    assert res["interval_seconds"] == 5
    assert res["max_failures"] == 3
    assert res["is_active"] is True


def test_chaos_tick_execution():
    """Verify link failure injection, route recomputation, EventStore logging, and postmortem."""
    session_id = "test_session"
    net_service.reset_network(session_id)
    baseline_edges = net_service.get_active_graph(session_id).edge_count()

    # Start chaos
    start_chaos(session_id=session_id, interval_seconds=5, max_failures=5)

    # Execute one tick
    result = chaos_tick(session_id=session_id)

    # 1. Edge severance
    assert result["status"] == "success"
    assert result["tick_number"] == 1
    assert "killed_edge" in result
    ke = result["killed_edge"]
    g = net_service.get_active_graph(session_id)
    assert not g.has_edge(ke["u"], ke["v"])
    assert not g.has_edge(ke["v"], ke["u"])
    assert result["remaining_edges"] == baseline_edges - 2
    assert g.edge_count() == baseline_edges - 2

    # 2. Route recomputation
    assert "before" in result and "after" in result
    assert "path" in result["before"]
    assert "path" in result["after"]

    # 3. EventStore logging
    events = get_event_store().list_events(session_id=session_id, limit=5)
    failure_ev = next((e for e in events if e.type == "failure_simulation"), None)
    assert failure_ev is not None
    assert failure_ev.inputs.get("chaos_mode") is True

    # 4. Automated Postmortem generation
    assert "postmortem" in result
    pm = result["postmortem"]
    assert pm["status"] == "success"
    assert "markdown" in pm
    assert "# Incident Postmortem:" in pm["markdown"]


def test_chaos_auto_reset_after_m_failures():
    """Verify that after M failures, the topology is automatically restored and chaos is stopped."""
    session_id = "test_session"
    net_service.reset_network(session_id)
    baseline_edges = net_service.get_active_graph(session_id).edge_count()

    # Configure chaos for M = 2 failures
    start_chaos(session_id=session_id, interval_seconds=5, max_failures=2)

    # Tick 1
    tick1 = chaos_tick(session_id=session_id)
    assert tick1["tick_number"] == 1
    assert tick1["auto_reset_triggered"] is False
    assert tick1["is_active"] is True
    assert net_service.get_active_graph(session_id).edge_count() == baseline_edges - 2

    # Tick 2 (should trigger auto-reset)
    tick2 = chaos_tick(session_id=session_id)
    assert tick2["tick_number"] == 2
    assert tick2["auto_reset_triggered"] is True
    assert tick2["is_active"] is False

    # Check topology restored
    assert net_service.get_active_graph(session_id).edge_count() == baseline_edges

    # Check session is inactive
    status = get_chaos_status(session_id=session_id)
    assert status["is_active"] is False

    # Calling tick again raises error
    with pytest.raises(ValueError) as excinfo:
        chaos_tick(session_id=session_id)
    assert "not currently active" in str(excinfo.value)


def test_chaos_stop_and_restore():
    """Verify manual stop button restores the topology to baseline."""
    session_id = "test_session"
    net_service.reset_network(session_id)
    baseline_edges = net_service.get_active_graph(session_id).edge_count()

    start_chaos(session_id=session_id, interval_seconds=5, max_failures=10)
    chaos_tick(session_id=session_id)
    assert net_service.get_active_graph(session_id).edge_count() == baseline_edges - 2

    # Stop with restore
    stop_res = stop_chaos(session_id=session_id, restore_topology=True)
    assert stop_res["status"] == "stopped"
    assert stop_res["topology_restored"] is True
    assert stop_res["is_active"] is False

    # Topology restored
    assert net_service.get_active_graph(session_id).edge_count() == baseline_edges


def test_chaos_session_isolation():
    """Verify two concurrent sessions have isolated chaos loops and states."""
    session_a = "session_a"
    session_b = "session_b"

    start_chaos(session_id=session_a, interval_seconds=5, max_failures=3)
    start_chaos(session_id=session_b, interval_seconds=10, max_failures=8)

    chaos_tick(session_id=session_a)
    chaos_tick(session_id=session_a)

    status_a = get_chaos_status(session_a)
    status_b = get_chaos_status(session_b)

    assert status_a["failure_count"] == 2
    assert status_a["max_failures"] == 3
    assert status_b["failure_count"] == 0
    assert status_b["max_failures"] == 8


def test_chaos_api_endpoints():
    """Verify /api/chaos/start, /api/chaos/tick, /api/chaos/status, /api/chaos/stop."""
    client = app.test_client()
    headers = {"X-Session-ID": "test_api_chaos"}

    # 1. Invalid interval < 5 rejected with 400
    resp_bad = client.post("/api/chaos/start", json={"interval_seconds": 3}, headers=headers)
    assert resp_bad.status_code == 400
    assert "at least 5 seconds" in resp_bad.get_json()["error"]

    # 2. Valid start
    resp_start = client.post(
        "/api/chaos/start",
        json={"interval_seconds": 5, "max_failures": 2},
        headers=headers,
    )
    assert resp_start.status_code == 200
    assert resp_start.get_json()["status"] == "started"

    # 3. Status endpoint
    resp_status = client.get("/api/chaos/status", headers=headers)
    assert resp_status.status_code == 200
    assert resp_status.get_json()["is_active"] is True

    # 4. Tick endpoint
    resp_tick = client.post("/api/chaos/tick", headers=headers)
    assert resp_tick.status_code == 200
    data_tick = resp_tick.get_json()
    assert data_tick["tick_number"] == 1
    assert "killed_edge" in data_tick
    assert "postmortem" in data_tick

    # 5. Stop endpoint
    resp_stop = client.post("/api/chaos/stop", json={"restore_topology": True}, headers=headers)
    assert resp_stop.status_code == 200
    assert resp_stop.get_json()["status"] == "stopped"
