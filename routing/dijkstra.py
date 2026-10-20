"""Dijkstra Single-Source Shortest Path (SSSP) algorithm from scratch.

Features:
- Hand-written with Python's standard library binary min-heap (heapq).
- Arbitrary directed weighted graph support with non-negative edge weights.
- Explicit validation raising ValueError if any negative edge weight exists.
- Empirical operation counter tracking heap operations and edge relaxations.
- Shortest path reconstruction and lowest-latency CDN edge server discovery.
"""

import heapq
from typing import Dict, List, Optional, Tuple, Any
from graph.network import Graph


class DijkstraResult:
    """Encapsulates the output of Dijkstra execution."""

    def __init__(
        self,
        source: str,
        distances: Dict[str, float],
        predecessors: Dict[str, Optional[str]],
        operations: int,
    ):
        self.source = source
        self.distances = distances
        self.predecessors = predecessors
        self.operations = operations

    def get_path(self, target: str) -> Optional[List[str]]:
        """Reconstruct shortest path from source to target.

        Returns:
            List of node IDs in order [source, ..., target], or None if unreachable.
        """
        if self.distances.get(target, float("inf")) == float("inf"):
            return None

        if target == self.source:
            return [self.source]

        path = []
        curr: Optional[str] = target
        visited = set()

        while curr is not None:
            if curr in visited:
                # Cycle detected in predecessor chain
                return None
            visited.add(curr)
            path.append(curr)
            if curr == self.source:
                break
            curr = self.predecessors.get(curr)

        if not path or path[-1] != self.source:
            return None

        path.reverse()
        return path

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "distances": self.distances,
            "operations": self.operations,
        }


def dijkstra(graph: Graph, source: str) -> DijkstraResult:
    """Compute single-source shortest paths from source using Dijkstra's algorithm.

    Args:
        graph: Graph instance.
        source: ID of the source vertex.

    Returns:
        DijkstraResult containing distances, predecessor map, and operation count.

    Raises:
        ValueError: If source node does not exist in graph or if any edge has negative latency.
    """
    if not graph.has_node(source):
        raise ValueError(f"Source node '{source}' not found in graph.")

    # Validate that no negative-weight edge exists anywhere in the graph
    all_edges = graph.get_edges()
    for edge in all_edges:
        if edge.latency < 0:
            raise ValueError(
                f"Dijkstra does not support negative edge weights: edge ({edge.u} -> {edge.v}) has negative latency {edge.latency}."
            )

    node_ids = list(graph.nodes.keys())
    distances: Dict[str, float] = {nid: float("inf") for nid in node_ids}
    predecessors: Dict[str, Optional[str]] = {nid: None for nid in node_ids}
    distances[source] = 0.0

    operations = 0

    # Priority queue storing (distance, node_id) tuples
    pq: List[Tuple[float, str]] = [(0.0, source)]
    heapq.heapify(pq)
    visited = set()

    while pq:
        curr_dist, u = heapq.heappop(pq)
        operations += 1  # 1 heap extraction / comparison operation

        if u in visited:
            continue
        visited.add(u)

        if curr_dist > distances[u]:
            continue

        neighbors = graph.adj.get(u, {})
        for v, edge in neighbors.items():
            operations += 1  # 1 edge examination / comparison
            weight = edge.latency

            if distances[u] + weight < distances[v]:
                distances[v] = distances[u] + weight
                predecessors[v] = u
                heapq.heappush(pq, (distances[v], v))
                operations += 1  # 1 heap insertion operation

    return DijkstraResult(
        source=source,
        distances=distances,
        predecessors=predecessors,
        operations=operations,
    )


def find_best_edge_server_dijkstra(
    graph: Graph,
    user_region_id: str,
) -> Dict[str, Any]:
    """Find lowest-latency edge server from user_region_id using Dijkstra.

    Returns:
        Dictionary with user_region, best_edge, latency, path, and operations.
    """
    dijk_res = dijkstra(graph, user_region_id)
    edge_servers = graph.get_nodes_by_type("edge_server")

    best_edge_id: Optional[str] = None
    min_latency = float("inf")

    for es in edge_servers:
        dist = dijk_res.distances.get(es.id, float("inf"))
        if dist < min_latency:
            min_latency = dist
            best_edge_id = es.id

    best_path = dijk_res.get_path(best_edge_id) if best_edge_id else None

    return {
        "user_region": user_region_id,
        "best_edge": best_edge_id,
        "latency": min_latency if min_latency != float("inf") else None,
        "path": best_path,
        "operations": dijk_res.operations,
        "algorithm": "Dijkstra",
    }
