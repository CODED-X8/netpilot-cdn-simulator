"""Unit tests for Propose, Simulate, Verify Mitigations Engine (Milestone M7).

Tests:
1. Mitigation candidate simulation on isolated graph copies without live graph mutation.
2. Deterministic ranking strictly based on measured metrics (throughput descending, latency ascending).
3. Rejection and discarding of malformed/invalid candidates (non-existent nodes, negative values).
4. Safety confirmation gate on live mitigation application.
5. REST API endpoints POST /api/mitigations/propose and /api/mitigations/apply.
6. Copilot agent integration with propose_mitigations tool.
"""

import pytest
from flask import Flask

import services.network_service as net_service
from services.mitigation_service import (
    propose_and_simulate_mitigations,
    apply_mitigation,
)
from copilot.agent import run_copilot_chat
from copilot.llm_provider import FakeLLMProvider
from dashboard.app import app


@pytest.fixture
def fresh_session():
    """Ensure a clean baseline graph session for testing."""
    session = "test_mitigation_session"
    net_service.reset_network(session_id=session)
    return session


def test_simulation_on_graph_copies_preserves_live_graph(fresh_session):
    """Verify that simulating candidate changes leaves the active live graph unmodified."""
    session = fresh_session
    graph = net_service.get_active_graph(session)
    orig_node_count = len(graph.nodes)
    orig_edge_count = len(graph.edges)

    res = propose_and_simulate_mitigations(goal="maximize throughput", session_id=session)

    assert res["status"] == "success"
    assert len(res["ranked_candidates"]) > 0

    # Ensure live active graph was NOT mutated during simulation
    graph_after = net_service.get_active_graph(session)
    assert len(graph_after.nodes) == orig_node_count
    assert len(graph_after.edges) == orig_edge_count


def test_deterministic_ranking_by_measured_metrics(fresh_session):
    """Verify candidates are ranked strictly by measured delta metric, not textual rationale."""
    session = fresh_session

    # Throughput ranking (descending delta max flow)
    res_flow = propose_and_simulate_mitigations(goal="maximize throughput", session_id=session)
    cands_flow = res_flow["ranked_candidates"]
    assert len(cands_flow) >= 2
    for i in range(len(cands_flow) - 1):
        flow_i = cands_flow[i]["measured_impact"]["delta_max_flow_mbps"]
        flow_next = cands_flow[i + 1]["measured_impact"]["delta_max_flow_mbps"]
        assert flow_i >= flow_next

    # Latency ranking (ascending delta average latency)
    res_lat = propose_and_simulate_mitigations(goal="minimize latency", session_id=session)
    cands_lat = res_lat["ranked_candidates"]
    assert len(cands_lat) >= 2
    for i in range(len(cands_lat) - 1):
        lat_i = cands_lat[i]["measured_impact"]["delta_avg_latency_ms"]
        lat_next = cands_lat[i + 1]["measured_impact"]["delta_avg_latency_ms"]
        assert lat_i <= lat_next


def test_invalid_candidates_are_discarded(fresh_session):
    """Verify invalid proposals (missing nodes, negative capacity, invalid actions) are safely discarded."""
    session = fresh_session

    custom_candidates = [
        {
            "action": "add_edge",
            "u": "ghost_node_1",
            "v": "edge_1",
            "value": 10.0,
            "rationale": "Invalid because node does not exist",
        },
        {
            "action": "increase_capacity",
            "u": "user_1",
            "v": "edge_1",
            "value": -100.0,
            "rationale": "Invalid because capacity is negative",
        },
        {
            "action": "invalid_action_type",
            "u": "user_1",
            "v": "edge_1",
            "value": 50.0,
            "rationale": "Invalid because action is unsupported",
        },
        {
            "action": "increase_capacity",
            "u": "origin_1",
            "v": "edge_1",
            "value": 1500.0,
            "rationale": "Valid candidate",
        },
    ]

    res = propose_and_simulate_mitigations(
        goal="maximize throughput",
        session_id=session,
        candidates=custom_candidates,
    )

    assert len(res["discarded_candidates"]) == 3
    assert len(res["ranked_candidates"]) == 1
    assert res["ranked_candidates"][0]["action"] == "increase_capacity"


def test_apply_mitigation_safety_confirmation(fresh_session):
    """Verify applying mitigation requires explicit user confirmation."""
    session = fresh_session
    graph = net_service.get_active_graph(session)
    orig_edges = len(graph.edges)

    candidate = {
        "action": "add_edge",
        "u": "user_1",
        "v": "origin_1",
        "proposed_value": 12.0,
        "bandwidth_capacity": 500.0,
    }

    # Attempt without confirmed=True
    unconf_res = apply_mitigation(candidate, session_id=session, confirmed=False)
    assert unconf_res["status"] == "confirmation_required"
    assert len(graph.edges) == orig_edges

    # Attempt with confirmed=True
    conf_res = apply_mitigation(candidate, session_id=session, confirmed=True)
    assert conf_res["status"] == "success"
    assert "event_id" in conf_res
    assert len(graph.edges) > orig_edges


def test_mitigations_api_endpoints(fresh_session):
    """Test Flask endpoints /api/mitigations/propose and /api/mitigations/apply."""
    client = app.test_client()

    # 1. Propose endpoint
    resp_prop = client.post("/api/mitigations/propose", json={"goal": "maximize throughput"})
    assert resp_prop.status_code == 200
    prop_data = resp_prop.get_json()
    assert "ranked_candidates" in prop_data
    assert len(prop_data["ranked_candidates"]) > 0

    best_cand = prop_data["ranked_candidates"][0]

    # 2. Apply endpoint without confirmation
    resp_app_unconf = client.post("/api/mitigations/apply", json={"candidate": best_cand, "confirmed": False})
    assert resp_app_unconf.status_code == 200
    assert resp_app_unconf.get_json()["status"] == "confirmation_required"

    # 3. Apply endpoint with confirmation
    resp_app_conf = client.post("/api/mitigations/apply", json={"candidate": best_cand, "confirmed": True})
    assert resp_app_conf.status_code == 200
    data_conf = resp_app_conf.get_json()
    assert data_conf["status"] == "success"
    assert "network" in data_conf


def test_copilot_agent_propose_mitigations():
    """Verify Copilot agent executes propose_mitigations tool."""
    fake_provider = FakeLLMProvider()
    resp = run_copilot_chat(
        message="Please propose mitigations to maximize throughput",
        session_id="test_pm_agent_session",
        custom_provider=fake_provider,
    )

    assert resp["grounding_verified"] is True
    assert any(t["tool"] == "propose_mitigations" for t in resp["tools_used"])
    assert "propose_mitigations" in resp["answer"].lower()
