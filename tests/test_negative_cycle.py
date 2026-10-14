"""Tests for negative-weight edge handling and negative-weight cycle detection."""

import pytest
from graph.network import Graph
from routing.bellman_ford import bellman_ford, NegativeCycleException
from routing.floyd_warshall import floyd_warshall


def test_negative_weight_without_cycle():
    """Graph with negative edge weights but NO negative cycles.

    Both Bellman-Ford and Floyd-Warshall must compute correct shortest paths.
    """
    g = Graph()
    g.add_node("A", "user_region")
    g.add_node("B", "edge_server")
    g.add_node("C", "edge_server")

    # A -> B (5), B -> C (-2), A -> C (4)
    # Path A -> B -> C has cost 5 - 2 = 3 < 4
    g.add_edge("A", "B", latency=5.0)
    g.add_edge("B", "C", latency=-2.0)
    g.add_edge("A", "C", latency=4.0)

    bf = bellman_ford(g, "A")
    assert bf.distances["C"] == 3.0
    assert bf.get_path("C") == ["A", "B", "C"]

    fw = floyd_warshall(g)
    assert fw.get_distance("A", "C") == 3.0
    assert fw.get_path("A", "C") == ["A", "B", "C"]


def test_negative_weight_cycle_detection_bellman_ford():
    """Graph with a negative cycle: A -> B (1), B -> C (-4), C -> A (2).

    Sum of cycle = 1 - 4 + 2 = -1 < 0.
    Bellman-Ford must raise NegativeCycleException.
    """
    g = Graph()
    g.add_node("A", "user_region")
    g.add_node("B", "edge_server")
    g.add_node("C", "edge_server")

    g.add_edge("A", "B", latency=1.0)
    g.add_edge("B", "C", latency=-4.0)
    g.add_edge("C", "A", latency=2.0)

    with pytest.raises(NegativeCycleException) as exc_info:
        bellman_ford(g, "A")

    assert "Negative-weight cycle detected" in str(exc_info.value)


def test_negative_weight_cycle_detection_floyd_warshall():
    """Floyd-Warshall must raise NegativeCycleException when diagonal entry becomes negative."""
    g = Graph()
    g.add_node("A", "user_region")
    g.add_node("B", "edge_server")
    g.add_node("C", "edge_server")

    g.add_edge("A", "B", latency=1.0)
    g.add_edge("B", "C", latency=-4.0)
    g.add_edge("C", "A", latency=2.0)

    with pytest.raises(NegativeCycleException):
        floyd_warshall(g)
