"""Unit tests for Max Flow algorithms (Edmonds-Karp and Ford-Fulkerson).

Includes:
1. Hand-verified 6-node ground-truth graph.
2. Max-flow min-cut theorem verification (max_flow == min_cut_capacity).
3. Disconnected sink test verifying 0 flow.
4. Multiple sinks via super-sink.
5. Cross-validation against networkx.maximum_flow on 50 random graphs.
"""

import pytest
import networkx as nx

from graph.network import Graph
from graph.generator import generate_cdn_topology, generate_random_benchmark_graph
from routing.max_flow import edmonds_karp, ford_fulkerson, compute_max_flow


@pytest.fixture
def handcrafted_flow_network() -> Graph:
    """Create a 6-node flow network with known ground-truth max flow of 19.0."""
    g = Graph()
    g.add_node("s", "origin")
    g.add_node("a", "edge_server")
    g.add_node("b", "edge_server")
    g.add_node("c", "edge_server")
    g.add_node("d", "edge_server")
    g.add_node("t", "user_region")

    g.add_edge("s", "a", latency=10.0, bandwidth_capacity=10.0)
    g.add_edge("s", "b", latency=10.0, bandwidth_capacity=10.0)
    g.add_edge("a", "b", latency=10.0, bandwidth_capacity=2.0)
    g.add_edge("a", "c", latency=10.0, bandwidth_capacity=4.0)
    g.add_edge("a", "d", latency=10.0, bandwidth_capacity=8.0)
    g.add_edge("b", "d", latency=10.0, bandwidth_capacity=9.0)
    g.add_edge("c", "t", latency=10.0, bandwidth_capacity=10.0)
    g.add_edge("d", "c", latency=10.0, bandwidth_capacity=6.0)
    g.add_edge("d", "t", latency=10.0, bandwidth_capacity=10.0)

    return g


def test_handcrafted_max_flow(handcrafted_flow_network: Graph):
    """Verify both algorithms produce exact ground truth flow of 19.0 on handcrafted graph."""
    res_ek = edmonds_karp(handcrafted_flow_network, source="s", sinks="t")
    res_ff = ford_fulkerson(handcrafted_flow_network, source="s", sinks="t")

    assert res_ek.max_flow == 19.0
    assert res_ff.max_flow == 19.0
    assert res_ek.augmenting_paths > 0
    assert res_ff.augmenting_paths > 0
    assert res_ek.operations > 0
    assert res_ff.operations > 0

    # Max flow equals min-cut capacity
    assert pytest.approx(res_ek.max_flow, rel=1e-5) == res_ek.min_cut_capacity
    assert pytest.approx(res_ff.max_flow, rel=1e-5) == res_ff.min_cut_capacity
    assert len(res_ek.min_cut_edges) > 0


def test_disconnected_sink():
    """Verify that a disconnected sink yields 0 flow and 0 augmenting paths."""
    g = Graph()
    g.add_node("s", "origin")
    g.add_node("a", "edge_server")
    g.add_node("t", "user_region")

    g.add_edge("s", "a", latency=5.0, bandwidth_capacity=500.0)
    # Note: no path to t

    res_ek = edmonds_karp(g, source="s", sinks="t")
    res_ff = ford_fulkerson(g, source="s", sinks="t")

    assert res_ek.max_flow == 0.0
    assert res_ff.max_flow == 0.0
    assert res_ek.augmenting_paths == 0
    assert res_ff.augmenting_paths == 0
    assert len(res_ek.min_cut_edges) == 0


def test_multi_sink_super_sink():
    """Verify multi-sink flow distribution via super-sink."""
    g = Graph()
    g.add_node("origin", "origin")
    g.add_node("hub", "edge_server")
    g.add_node("sink_1", "user_region")
    g.add_node("sink_2", "user_region")

    g.add_edge("origin", "hub", latency=10.0, bandwidth_capacity=1000.0)
    g.add_edge("hub", "sink_1", latency=5.0, bandwidth_capacity=400.0)
    g.add_edge("hub", "sink_2", latency=5.0, bandwidth_capacity=500.0)

    res = edmonds_karp(g, source="origin", sinks=["sink_1", "sink_2"])
    assert res.max_flow == 900.0
    assert pytest.approx(res.max_flow, rel=1e-5) == res.min_cut_capacity
    assert ("hub", "sink_1") in res.min_cut_edges
    assert ("hub", "sink_2") in res.min_cut_edges


def test_networkx_cross_validation_50_random_graphs():
    """Cross-validate flow value against networkx.maximum_flow on 50 random topologies."""
    for seed in range(50):
        # Generate random graph with 8-20 nodes
        num_nodes = 8 + (seed % 13)
        g = generate_random_benchmark_graph(
            num_nodes=num_nodes,
            edge_density=0.35,
            min_latency=5.0,
            max_latency=50.0,
            seed=1000 + seed,
        )

        nodes = list(g.nodes.keys())
        source = nodes[0]
        sink = nodes[-1]

        # Convert to NetworkX DiGraph
        nx_g = nx.DiGraph()
        for edge in g.get_edges():
            nx_g.add_edge(edge.u, edge.v, capacity=edge.bandwidth_capacity)

        # Compute NetworkX ground truth
        nx_flow_val, _ = nx.maximum_flow(nx_g, source, sink, capacity="capacity")

        # Compute our from-scratch Edmonds-Karp & Ford-Fulkerson
        our_ek = edmonds_karp(g, source, sink)
        our_ff = ford_fulkerson(g, source, sink)

        assert pytest.approx(our_ek.max_flow, abs=1e-3) == nx_flow_val, (
            f"Seed {seed}: EK flow {our_ek.max_flow} != NX flow {nx_flow_val}"
        )
        assert pytest.approx(our_ff.max_flow, abs=1e-3) == nx_flow_val, (
            f"Seed {seed}: FF flow {our_ff.max_flow} != NX flow {nx_flow_val}"
        )
        # Max flow equals min-cut capacity
        assert pytest.approx(our_ek.max_flow, abs=1e-3) == our_ek.min_cut_capacity
