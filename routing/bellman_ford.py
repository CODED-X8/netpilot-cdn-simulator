"""Bellman-Ford Single-Source Shortest Path (SSSP) algorithm from scratch.

Features:
- Arbitrary directed weighted graph support.
- Negative-weight cycle detection (Review 1 requirement).
- Empirical operation counter tracking edge relaxation comparisons.
- Shortest path reconstruction and best CDN edge server discovery.
"""

from typing import Dict, List, Optional, Tuple, Any
from graph.network import Graph


class NegativeCycleException(Exception):
    """Raised when a negative-weight cycle is detected in the graph."""
    pass


class BellmanFordResult:
    """Encapsulates the output of Bellman-Ford execution."""

    def __init__(
        self,
        source: str,
        distances: Dict[str, float],
        predecessors: Dict[str, Optional[str]],
        operations: int,
        has_negative_cycle: bool = False,
    ):
        self.source = source
        self.distances = distances
        self.predecessors = predecessors
        self.operations = operations
        self.has_negative_cycle = has_negative_cycle

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
            "has_negative_cycle": self.has_negative_cycle,
        }


def bellman_ford(
    graph: Graph,
    source: str,
    detect_negative_cycle: bool = True,
    early_stopping: bool = False,
) -> BellmanFordResult:
    """Compute single-source shortest paths from source using Bellman-Ford.

    Args:
        graph: Graph instance.
        source: ID of the source vertex.
        detect_negative_cycle: If True, executes the |V|-th pass to catch negative cycles.
        early_stopping: If True, terminates early if no relaxations occur in an iteration.
                        Default False ensures strict O(|V| * |E|) operation counting.

    Returns:
        BellmanFordResult containing distances, predecessor map, and operation count.

    Raises:
        ValueError: If source node does not exist in graph.
        NegativeCycleException: If a negative-weight cycle reachable from source is found.
    """
    if not graph.has_node(source):
        raise ValueError(f"Source node '{source}' not found in graph.")

    node_ids = list(graph.nodes.keys())
    num_vertices = len(node_ids)
    all_edges = graph.get_edges()
    num_edges = len(all_edges)

    distances: Dict[str, float] = {nid: float("inf") for nid in node_ids}
    predecessors: Dict[str, Optional[str]] = {nid: None for nid in node_ids}
    distances[source] = 0.0

    operations = 0

    # Step 1: Relax edges |V| - 1 times
    for iteration in range(num_vertices - 1):
        any_updated = False
        for edge in all_edges:
            operations += 1  # 1 edge examination / comparison
            u, v, weight = edge.u, edge.v, edge.latency

            if distances[u] != float("inf"):
                if distances[u] + weight < distances[v]:
                    distances[v] = distances[u] + weight
                    predecessors[v] = u
                    any_updated = True

        if early_stopping and not any_updated:
            break

    # Step 2: Check for negative-weight cycles (|V|-th pass)
    if detect_negative_cycle:
        for edge in all_edges:
            operations += 1  # 1 edge examination / comparison
            u, v, weight = edge.u, edge.v, edge.latency

            if distances[u] != float("inf"):
                # Tolerance check to prevent floating-point inaccuracy
                if distances[u] + weight < distances[v] - 1e-9:
                    raise NegativeCycleException(
                        f"Negative-weight cycle detected reachable via edge ({u} -> {v}) "
                        f"with weight {weight} (dist[{u}]={distances[u]}, dist[{v}]={distances[v]})"
                    )

    return BellmanFordResult(
        source=source,
        distances=distances,
        predecessors=predecessors,
        operations=operations,
        has_negative_cycle=False,
    )


def find_best_edge_server_bf(
    graph: Graph,
    user_region_id: str,
    early_stopping: bool = False,
) -> Dict[str, Any]:
    """Find lowest-latency edge server from user_region_id using Bellman-Ford.

    Returns:
        Dictionary with best_edge_id, latency, path, and operations.
    """
    bf_res = bellman_ford(graph, user_region_id, early_stopping=early_stopping)
    edge_servers = graph.get_nodes_by_type("edge_server")

    best_edge_id: Optional[str] = None
    min_latency = float("inf")

    for es in edge_servers:
        dist = bf_res.distances.get(es.id, float("inf"))
        if dist < min_latency:
            min_latency = dist
            best_edge_id = es.id

    best_path = bf_res.get_path(best_edge_id) if best_edge_id else None

    return {
        "user_region": user_region_id,
        "best_edge": best_edge_id,
        "latency": min_latency if min_latency != float("inf") else None,
        "path": best_path,
        "operations": bf_res.operations,
        "algorithm": "Bellman-Ford",
    }
