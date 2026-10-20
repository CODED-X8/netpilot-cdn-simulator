"""Unit and cross-validation tests for Dijkstra SSSP Engine (Milestone X1)."""

import pytest
from graph.network import Graph
from graph.generator import generate_cdn_topology, generate_random_benchmark_graph
from routing.dijkstra import dijkstra, find_best_edge_server_dijkstra, DijkstraResult
from routing.bellman_ford import bellman_ford
from routing.floyd_warshall import floyd_warshall
import services.network_service as net_service


def test_handcrafted_dijkstra():
    """Verify Dijkstra computes exact shortest paths on a known 5-node graph."""
    g = Graph()
    g.add_node("A", "user_region")
    g.add_node("B", "transit")
    g.add_node("C", "transit")
    g.add_node("D", "transit")
    g.add_node("E", "edge_server")

    # A -> B (4), A -> C (2)
    # C -> B (1), C -> D (5)
    # B -> D (1), B -> E (6)
    # D -> E (1)
    g.add_edge("A", "B", latency=4.0)
    g.add_edge("A", "C", latency=2.0)
    g.add_edge("C", "B", latency=1.0)
    g.add_edge("C", "D", latency=5.0)
    g.add_edge("B", "D", latency=1.0)
    g.add_edge("B", "E", latency=6.0)
    g.add_edge("D", "E", latency=1.0)

    res = dijkstra(g, "A")
    assert isinstance(res, DijkstraResult)
    assert res.distances["A"] == 0.0
    assert res.distances["C"] == 2.0
    assert res.distances["B"] == 3.0  # A -> C -> B (2 + 1 = 3)
    assert res.distances["D"] == 4.0  # A -> C -> B -> D (2 + 1 + 1 = 4)
    assert res.distances["E"] == 5.0  # A -> C -> B -> D -> E (4 + 1 = 5)

    path = res.get_path("E")
    assert path == ["A", "C", "B", "D", "E"]
    assert res.operations > 0


def test_dijkstra_negative_edge_raises_error():
    """Verify Dijkstra strictly rejects negative edge weights with a clear error."""
    g = Graph()
    g.add_node("u", "user_region")
    g.add_node("v", "edge_server")
    g.add_edge("u", "v", latency=-2.5)

    with pytest.raises(ValueError) as exc_info:
        dijkstra(g, "u")
    assert "Dijkstra does not support negative edge weights" in str(exc_info.value)
    assert "latency -2.5" in str(exc_info.value)


def test_dijkstra_disconnected_node():
    """Verify disconnected node has distance inf and get_path returns None."""
    g = Graph()
    g.add_node("u", "user_region")
    g.add_node("v", "edge_server")
    g.add_node("isolated", "edge_server")
    g.add_edge("u", "v", latency=10.0)

    res = dijkstra(g, "u")
    assert res.distances["u"] == 0.0
    assert res.distances["v"] == 10.0
    assert res.distances["isolated"] == float("inf")
    assert res.get_path("isolated") is None


def test_dijkstra_edge_server_discovery():
    """Verify find_best_edge_server_dijkstra identifies lowest-latency edge server."""
    g = generate_cdn_topology(num_origins=1, num_edges=5, num_users=3, seed=42)
    user_node = g.get_nodes_by_type("user_region")[0].id

    res = find_best_edge_server_dijkstra(g, user_node)
    assert res["user_region"] == user_node
    assert res["best_edge"] is not None
    assert res["latency"] > 0
    assert res["path"][0] == user_node
    assert res["path"][-1] == res["best_edge"]
    assert res["algorithm"] == "Dijkstra"
    assert res["operations"] > 0


@pytest.mark.parametrize("seed", [10, 42, 99, 123, 777])
def test_dijkstra_cross_validation_random_graphs(seed):
    """Cross-validate Dijkstra against Bellman-Ford and Floyd-Warshall on random non-negative graphs."""
    g = generate_random_benchmark_graph(num_nodes=15, edge_density=0.3, seed=seed)
    source = list(g.nodes.keys())[0]

    dijk_res = dijkstra(g, source)
    bf_res = bellman_ford(g, source, early_stopping=False)
    fw_res = floyd_warshall(g, detect_negative_cycle=True)

    for nid in g.nodes:
        dijk_dist = dijk_res.distances[nid]
        bf_dist = bf_res.distances[nid]
        fw_dist = fw_res.get_distance(source, nid)

        if dijk_dist == float("inf"):
            assert bf_dist == float("inf")
            assert fw_dist == float("inf")
        else:
            assert dijk_dist == pytest.approx(bf_dist, rel=1e-5)
            assert dijk_dist == pytest.approx(fw_dist, rel=1e-5)


def test_network_service_dijkstra_and_compare_three_way():
    """Verify service layer shortest_path with dijkstra and three-way agreement in compare_algorithms."""
    g = generate_cdn_topology(num_origins=1, num_edges=4, num_users=2, seed=100)
    user_id = g.get_nodes_by_type("user_region")[0].id

    # 1. Shortest path with Dijkstra
    route_dijk = net_service.shortest_path(source=user_id, algo="dijkstra", graph=g)
    assert route_dijk["algorithm"] == "Dijkstra"
    assert route_dijk["complexity"] == "O((|V| + |E|) log |V|)"
    assert route_dijk["latency"] > 0
    assert route_dijk["operations"] > 0

    # 2. Compare algorithms (three-way agreement)
    cmp_res = net_service.compare_algorithms(source=user_id, graph=g)
    assert "dijkstra" in cmp_res
    assert "bellman_ford" in cmp_res
    assert "floyd_warshall" in cmp_res

    ag = cmp_res["agreement"]
    assert ag["three_way_matched"] is True
    assert ag["matched"] is True
    assert ag["best_edge_match"] is True
    assert ag["latency_diff"] == 0.0
