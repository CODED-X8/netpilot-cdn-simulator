"""Tests for service layer and event store."""

import pytest
import os
from graph.generator import generate_cdn_topology
from services.network_service import (
    shortest_path,
    compare_algorithms,
    kill_edge,
    reset_network,
    what_if,
    max_flow,
    find_bottleneck,
    get_metrics,
    list_nodes,
    set_active_graph,
    get_active_graph,
)
from storage.event_store import EventStore


def test_event_store_crud(tmp_path):
    db_file = str(tmp_path / "test_events.db")
    store = EventStore(db_path=db_file)

    event = store.log_event(
        event_type="test_event",
        session_id="s123",
        topology_name="Test Topology",
        inputs={"param": 42},
        results={"success": True},
        ops_count=100,
        compute_time_ms=1.23,
    )

    assert event.id is not None
    fetched = store.get_event(event.id)
    assert fetched is not None
    assert fetched.session_id == "s123"
    assert fetched.inputs["param"] == 42
    assert fetched.ops_count == 100

    events = store.list_events(session_id="s123")
    assert len(events) == 1
    assert events[0].id == event.id


def test_service_functions():
    session_id = "test_service_session"
    reset_network(session_id=session_id)

    # 1. list_nodes
    nodes = list_nodes(session_id=session_id)
    assert len(nodes) == 20

    # 2. get_metrics
    metrics = get_metrics(session_id=session_id)
    assert metrics["node_count"] == 20
    assert metrics["edge_count"] > 0

    # 3. shortest_path
    sp = shortest_path(source="user_1", session_id=session_id)
    assert sp["best_edge"] is not None
    assert sp["latency"] is not None
    assert len(sp["path"]) >= 2

    # 4. compare_algorithms
    cmp_res = compare_algorithms(source="user_3", session_id=session_id)
    assert cmp_res["agreement"]["matched"] is True

    # 5. max_flow & find_bottleneck
    flow_res = max_flow(session_id=session_id)
    assert flow_res["max_flow"] > 0
    bottleneck = find_bottleneck(session_id=session_id)
    assert bottleneck["max_flow"] == flow_res["max_flow"]
    assert len(bottleneck["bottleneck_edges"]) > 0

    # 6. what_if on a COPY
    g_before = get_active_graph(session_id)
    edge_count_before = g_before.edge_count()
    what_if_res = what_if(
        remove_edges=["user_1<->edge_1"],
        source="user_1",
        session_id=session_id,
    )
    # Ensure live graph was NOT mutated!
    assert g_before.edge_count() == edge_count_before
    assert what_if_res["before"]["best_edge"] is not None

    # 7. kill_edge
    kill_res = kill_edge(session_id=session_id)
    assert kill_res["status"] == "success"
    assert g_before.edge_count() == edge_count_before - 2 or g_before.edge_count() == edge_count_before - 1
