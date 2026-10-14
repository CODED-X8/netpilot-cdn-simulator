"""Hand-verifiable ground-truth test on a 6-node CDN topology.

Graph Schema:
  Nodes:
    - U1: user_region
    - E1, E2, E3, E4: edge_server
    - O1: origin

  Edges & Latencies (ms):
    - U1 -> E1 : 50
    - U1 -> E2 : 10
    - E2 -> E1 : 25   (Alternative path to E1: 10 + 25 = 35 < 50)
    - E2 -> E3 : 15   (Path to E3: 10 + 15 = 25)
    - E3 -> E4 : 12   (Path to E4: 25 + 12 = 37)
    - E1 -> E4 : 80
    - E4 -> O1 : 20   (Path to O1: 37 + 20 = 57)
    - E1 -> O1 : 100

Hand-computed Ground Truth from source U1:
  - dist(U1, U1) = 0,   path = [U1]
  - dist(U1, E2) = 10,  path = [U1, E2]
  - dist(U1, E3) = 25,  path = [U1, E2, E3]
  - dist(U1, E1) = 35,  path = [U1, E2, E1]        (relaxes initial 50ms direct edge)
  - dist(U1, E4) = 37,  path = [U1, E2, E3, E4]
  - dist(U1, O1) = 57,  path = [U1, E2, E3, E4, O1]
  - Best Edge Server from U1: E2 (10ms, path [U1, E2])
"""

import pytest
from graph.network import Graph
from routing.bellman_ford import bellman_ford, find_best_edge_server_bf
from routing.floyd_warshall import floyd_warshall, find_best_edge_server_fw


@pytest.fixture
def handcrafted_graph() -> Graph:
    g = Graph()
    g.add_node("U1", "user_region")
    g.add_node("E1", "edge_server")
    g.add_node("E2", "edge_server")
    g.add_node("E3", "edge_server")
    g.add_node("E4", "edge_server")
    g.add_node("O1", "origin")

    g.add_edge("U1", "E1", latency=50.0)
    g.add_edge("U1", "E2", latency=10.0)
    g.add_edge("E2", "E1", latency=25.0)
    g.add_edge("E2", "E3", latency=15.0)
    g.add_edge("E3", "E4", latency=12.0)
    g.add_edge("E1", "E4", latency=80.0)
    g.add_edge("E4", "O1", latency=20.0)
    g.add_edge("E1", "O1", latency=100.0)

    return g


def test_handcrafted_bellman_ford(handcrafted_graph: Graph):
    bf = bellman_ford(handcrafted_graph, "U1")

    # Verify distances match ground truth exactly
    assert bf.distances["U1"] == 0.0
    assert bf.distances["E2"] == 10.0
    assert bf.distances["E3"] == 25.0
    assert bf.distances["E1"] == 35.0
    assert bf.distances["E4"] == 37.0
    assert bf.distances["O1"] == 57.0

    # Verify paths match ground truth
    assert bf.get_path("U1") == ["U1"]
    assert bf.get_path("E2") == ["U1", "E2"]
    assert bf.get_path("E3") == ["U1", "E2", "E3"]
    assert bf.get_path("E1") == ["U1", "E2", "E1"]
    assert bf.get_path("E4") == ["U1", "E2", "E3", "E4"]
    assert bf.get_path("O1") == ["U1", "E2", "E3", "E4", "O1"]

    # Verify best edge server
    best = find_best_edge_server_bf(handcrafted_graph, "U1")
    assert best["best_edge"] == "E2"
    assert best["latency"] == 10.0
    assert best["path"] == ["U1", "E2"]
    assert best["operations"] > 0


def test_handcrafted_floyd_warshall(handcrafted_graph: Graph):
    fw = floyd_warshall(handcrafted_graph)

    # Verify distances match ground truth exactly
    assert fw.get_distance("U1", "U1") == 0.0
    assert fw.get_distance("U1", "E2") == 10.0
    assert fw.get_distance("U1", "E3") == 25.0
    assert fw.get_distance("U1", "E1") == 35.0
    assert fw.get_distance("U1", "E4") == 37.0
    assert fw.get_distance("U1", "O1") == 57.0

    # Verify paths match ground truth
    assert fw.get_path("U1", "U1") == ["U1"]
    assert fw.get_path("U1", "E2") == ["U1", "E2"]
    assert fw.get_path("U1", "E3") == ["U1", "E2", "E3"]
    assert fw.get_path("U1", "E1") == ["U1", "E2", "E1"]
    assert fw.get_path("U1", "E4") == ["U1", "E2", "E3", "E4"]
    assert fw.get_path("U1", "O1") == ["U1", "E2", "E3", "E4", "O1"]

    # Verify best edge server
    best = find_best_edge_server_fw(handcrafted_graph, "U1", fw)
    assert best["best_edge"] == "E2"
    assert best["latency"] == 10.0
    assert best["path"] == ["U1", "E2"]
    assert best["operations"] == 6 ** 3  # 6^3 = 216 comparisons
