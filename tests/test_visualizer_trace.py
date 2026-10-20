"""Tests for Milestone X2: Step-Through Visualizer and Algorithm Trace Mode.

Verifies:
1. Handcrafted Bellman-Ford trace mode: records step details (pass, edge, before/after, improvement)
   and guarantees trace final state equals normal result.
2. Handcrafted Floyd-Warshall trace mode: records step details (k index, pair, intermediate, before/after, improvement)
   and guarantees trace final state equals normal result.
3. Network service explain_route_trace: limits execution to topologies <= 30 nodes with clear error.
4. Dashboard REST API /api/routing/trace endpoint with validation.
"""

import pytest
from graph.network import Graph
from routing.bellman_ford import bellman_ford
from routing.floyd_warshall import floyd_warshall
from services.network_service import explain_route_trace, get_active_graph, reset_network
from dashboard.app import app


@pytest.fixture
def sample_campus_graph() -> Graph:
    """College campus topology with 10 nodes."""
    g = Graph()
    g.add_node("AB1", "user_region")
    g.add_node("AB2", "user_region")
    g.add_node("AB3", "user_region")
    g.add_node("AB4", "user_region")
    g.add_node("Hostel_A", "user_region")
    g.add_node("Hostel_B", "user_region")
    g.add_node("Central_Router", "transit")
    g.add_node("Core_Switch", "transit")
    g.add_node("Admin", "edge_server")
    g.add_node("DataCenter_Main", "origin")

    g.add_edge("AB1", "Central_Router", latency=8.0, bandwidth=100.0)
    g.add_edge("AB2", "Central_Router", latency=12.0, bandwidth=100.0)
    g.add_edge("AB3", "Core_Switch", latency=15.0, bandwidth=100.0)
    g.add_edge("AB4", "Core_Switch", latency=9.0, bandwidth=100.0)
    g.add_edge("Hostel_A", "Central_Router", latency=14.0, bandwidth=100.0)
    g.add_edge("Hostel_B", "Core_Switch", latency=18.0, bandwidth=100.0)
    g.add_edge("Central_Router", "Core_Switch", latency=5.0, bandwidth=500.0)
    g.add_edge("Central_Router", "Admin", latency=6.0, bandwidth=200.0)
    g.add_edge("Core_Switch", "Admin", latency=7.0, bandwidth=200.0)
    g.add_edge("Admin", "DataCenter_Main", latency=4.0, bandwidth=1000.0)
    return g


def test_bellman_ford_trace_final_state_equals_normal(sample_campus_graph):
    """Assert trace final state equals normal result for Bellman-Ford."""
    source = "AB1"
    normal_result = bellman_ford(sample_campus_graph, source, trace_mode=False)
    traced_result = bellman_ford(sample_campus_graph, source, trace_mode=True)

    # 1. Math equality
    assert traced_result.distances == normal_result.distances
    assert traced_result.predecessors == normal_result.predecessors
    assert traced_result.operations == normal_result.operations
    assert traced_result.has_negative_cycle == normal_result.has_negative_cycle

    # 2. Trace structure validation
    assert len(traced_result.trace) > 0
    improved_count = 0

    for step in traced_result.trace:
        assert "pass" in step
        assert "edge" in step
        assert "u" in step["edge"] and "v" in step["edge"] and "weight" in step["edge"]
        assert "dist_u" in step
        assert "dist_v_before" in step
        assert "dist_v_after" in step
        assert "improved" in step
        assert "distances" in step
        assert "explanation" in step
        assert isinstance(step["improved"], bool)
        if step["improved"]:
            improved_count += 1
            assert step["dist_v_after"] is not None

    assert improved_count > 0, "At least one relaxation should have improved a distance"

    # 3. Final step distance table matches normal distances
    last_step = traced_result.trace[-1]
    for node_id, normal_dist in normal_result.distances.items():
        expected = normal_dist if normal_dist != float("inf") else None
        assert last_step["distances"][node_id] == expected


def test_floyd_warshall_trace_final_state_equals_normal(sample_campus_graph):
    """Assert trace final state equals normal result for Floyd-Warshall."""
    normal_result = floyd_warshall(sample_campus_graph, trace_mode=False)
    traced_result = floyd_warshall(sample_campus_graph, trace_mode=True, source_focus="AB1")

    # 1. Math equality
    assert traced_result.dist == normal_result.dist
    assert traced_result.next_node == normal_result.next_node
    assert traced_result.operations == normal_result.operations
    assert traced_result.has_negative_cycle == normal_result.has_negative_cycle

    # 2. Trace structure validation
    assert len(traced_result.trace) > 0
    improved_count = 0

    for step in traced_result.trace:
        assert "k_index" in step
        assert "k_node" in step
        assert "pair" in step
        assert "edge" in step
        assert "intermediate" in step
        assert "dist_before" in step
        assert "dist_after" in step
        assert "improved" in step
        assert "distances" in step
        assert "explanation" in step
        assert isinstance(step["improved"], bool)
        if step["improved"]:
            improved_count += 1

    assert improved_count > 0, "Floyd-Warshall should record path improvements"


def test_trace_mode_on_multiple_random_topologies():
    """Verify trace state equality across different graph configurations."""
    import random
    rng = random.Random(42)

    g = Graph()
    nodes = [f"N{i}" for i in range(8)]
    for n in nodes:
        g.add_node(n, "transit")

    # Add random connected edges
    for i in range(len(nodes) - 1):
        g.add_edge(nodes[i], nodes[i+1], latency=float(rng.randint(2, 20)), bandwidth=100.0)
    for _ in range(10):
        u = rng.choice(nodes)
        v = rng.choice(nodes)
        if u != v and not g.has_edge(u, v):
            g.add_edge(u, v, latency=float(rng.randint(2, 30)), bandwidth=100.0)

    # Bellman-Ford check
    bf_normal = bellman_ford(g, "N0", trace_mode=False)
    bf_traced = bellman_ford(g, "N0", trace_mode=True)
    assert bf_normal.distances == bf_traced.distances
    assert bf_normal.predecessors == bf_traced.predecessors

    # Floyd-Warshall check
    fw_normal = floyd_warshall(g, trace_mode=False)
    fw_traced = floyd_warshall(g, trace_mode=True, source_focus="N0")
    assert fw_normal.dist == fw_traced.dist


def test_explain_route_trace_service_limits():
    """Verify that explain_route_trace enforces <= 30 nodes limit."""
    # Graph with 30 nodes: allowed
    g30 = Graph()
    for i in range(30):
        g30.add_node(f"node_{i}", "transit" if i > 0 else "user_region")
    for i in range(29):
        g30.add_edge(f"node_{i}", f"node_{i+1}", latency=5.0, bandwidth=100.0)

    res = explain_route_trace(source="node_0", algo="bellman_ford", graph=g30)
    assert res["node_count"] == 30
    assert len(res["steps"]) > 0

    # Graph with 31 nodes: raises ValueError
    g31 = Graph()
    for i in range(31):
        g31.add_node(f"node_{i}", "transit" if i > 0 else "user_region")
    for i in range(30):
        g31.add_edge(f"node_{i}", f"node_{i+1}", latency=5.0, bandwidth=100.0)

    with pytest.raises(ValueError) as excinfo:
        explain_route_trace(source="node_0", algo="bellman_ford", graph=g31)
    assert "limited to topologies with at most 30 nodes" in str(excinfo.value)


def test_trace_api_endpoint():
    """Test /api/routing/trace API endpoint."""
    client = app.test_client()

    # Reset to default sample topology
    reset_network()

    # 1. Bellman-Ford trace
    resp = client.post("/api/routing/trace", json={"user_id": "user_1", "algorithm": "bellman_ford"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["algorithm"] == "Bellman-Ford"
    assert data["source"] == "user_1"
    assert data["node_count"] <= 30
    assert "steps" in data
    assert len(data["steps"]) > 0

    # 2. Floyd-Warshall trace
    resp_fw = client.post("/api/routing/trace", json={"user_id": "user_1", "algorithm": "floyd_warshall"})
    assert resp_fw.status_code == 200
    data_fw = resp_fw.get_json()
    assert data_fw["algorithm"] == "Floyd-Warshall"
    assert len(data_fw["steps"]) > 0

    # 3. Missing user_id returns 400
    resp_bad = client.post("/api/routing/trace", json={"algorithm": "bellman_ford"})
    assert resp_bad.status_code == 400

    # 4. GET query params support
    resp_get = client.get("/api/routing/trace?user_id=user_1&algorithm=bellman_ford")
    assert resp_get.status_code == 200
