"""Unit tests for the Graph data model and CDN topology generator."""

import pytest
from graph.network import Graph, Node, Edge
from graph.generator import generate_cdn_topology, generate_random_benchmark_graph


def test_node_creation_and_validation():
    n1 = Node("origin_1", "origin", "Origin Datacenter")
    assert n1.id == "origin_1"
    assert n1.node_type == "origin"
    assert n1.label == "Origin Datacenter"

    with pytest.raises(ValueError):
        Node("bad_node", "invalid_type")


def test_graph_add_and_remove_nodes():
    g = Graph()
    g.add_node("u1", "user_region")
    g.add_node("e1", "edge_server")
    assert len(g) == 2
    assert g.has_node("u1")
    assert g.has_node("e1")
    assert not g.has_node("unknown")


def test_graph_edges_and_weights():
    g = Graph()
    g.add_edge("u1", "e1", latency=25.0, bandwidth_capacity=100.0)
    assert g.has_edge("u1", "e1")
    assert not g.has_edge("e1", "u1")  # Directed by default

    edge = g.get_edge("u1", "e1")
    assert edge is not None
    assert edge.latency == 25.0
    assert edge.bandwidth_capacity == 100.0


def test_graph_bidirectional_edge():
    g = Graph()
    g.add_edge("e1", "e2", latency=15.0, bidirectional=True)
    assert g.has_edge("e1", "e2")
    assert g.has_edge("e2", "e1")
    assert g.get_edge("e1", "e2").latency == 15.0
    assert g.get_edge("e2", "e1").latency == 15.0


def test_edge_removal_failure_simulation():
    g = Graph()
    g.add_edge("u1", "e1", latency=30.0, bidirectional=True)
    assert g.has_edge("u1", "e1")
    assert g.has_edge("e1", "u1")

    # Remove single direction
    assert g.remove_edge("u1", "e1", bidirectional=False)
    assert not g.has_edge("u1", "e1")
    assert g.has_edge("e1", "u1")

    # Remove reverse
    assert g.remove_edge("e1", "u1")
    assert not g.has_edge("e1", "u1")
    assert not g.remove_edge("nonexistent", "other")


def test_update_edge_weight_congestion_simulation():
    g = Graph()
    g.add_edge("u1", "e1", latency=20.0, bandwidth_capacity=100.0, bidirectional=True)
    
    # Simulate network congestion: latency spikes to 120ms
    success = g.update_edge_weight("u1", "e1", latency=120.0, bandwidth_capacity=20.0, bidirectional=True)
    assert success
    assert g.get_edge("u1", "e1").latency == 120.0
    assert g.get_edge("e1", "u1").latency == 120.0
    assert g.get_edge("u1", "e1").bandwidth_capacity == 20.0


def test_get_adjacency():
    g = Graph()
    g.add_edge("A", "B", 10.0)
    g.add_edge("A", "C", 20.0)
    g.add_edge("B", "C", 5.0)

    adj = g.get_adjacency()
    assert adj["A"] == {"B": 10.0, "C": 20.0}
    assert adj["B"] == {"C": 5.0}
    assert adj["C"] == {}


def test_cdn_generator_structure():
    g = generate_cdn_topology(num_origins=1, num_edges=8, num_users=5, seed=42)
    assert len(g.get_nodes_by_type("origin")) == 1
    assert len(g.get_nodes_by_type("edge_server")) == 8
    primary_users = [u for u in g.get_nodes_by_type("user_region") if u.metadata.get("tier") == "user"]
    assert len(primary_users) == 5
    assert g.edge_count() > 0

    # Ensure all user regions have at least one outgoing link
    for user in primary_users:
        neighbors = g.adj[user.id]
        assert len(neighbors) >= 1


def test_multi_hop_routing_guarantee():
    """Verify that remote user populations require 3+ hops to reach their optimal edge server."""
    from routing.bellman_ford import find_best_edge_server_bf
    g = generate_cdn_topology(seed=42)

    for uid in ["user_3", "user_4", "user_5"]:
        res = find_best_edge_server_bf(g, uid)
        assert res["best_edge"] is not None
        assert len(res["path"]) - 1 >= 3, f"Expected 3+ hops for {uid}, got path: {res['path']}"
