"""Floyd-Warshall All-Pairs Shortest Path (APSP) algorithm from scratch.

Features:
- Full O(|V|^3) dynamic programming matrix computation.
- Path reconstruction matrix (next_node).
- Negative cycle detection (dist[i][i] < 0).
- Empirical operation counter tracking inner loop comparisons.
- Best CDN edge server query resolution.
"""

from typing import Dict, List, Optional, Tuple, Any
from graph.network import Graph
from .bellman_ford import NegativeCycleException


class FloydWarshallResult:
    """Encapsulates the output of Floyd-Warshall execution."""

    def __init__(
        self,
        nodes: List[str],
        node_to_idx: Dict[str, int],
        dist_matrix: List[List[float]],
        next_matrix: List[List[Optional[int]]],
        operations: int,
        has_negative_cycle: bool = False,
        trace: Optional[List[Dict[str, Any]]] = None,
    ):
        self.nodes = nodes
        self.node_to_idx = node_to_idx
        self.idx_to_node = {i: n for n, i in node_to_idx.items()}
        self.dist = dist_matrix
        self.next_node = next_matrix
        self.operations = operations
        self.has_negative_cycle = has_negative_cycle
        self.trace = trace or []

    def get_distance(self, u: str, v: str) -> float:
        """Get shortest distance from node u to node v."""
        if u not in self.node_to_idx or v not in self.node_to_idx:
            return float("inf")
        i, j = self.node_to_idx[u], self.node_to_idx[v]
        return self.dist[i][j]

    def get_path(self, u: str, v: str) -> Optional[List[str]]:
        """Reconstruct shortest path from node u to node v.

        Returns:
            List of node IDs in sequence [u, ..., v], or None if unreachable.
        """
        if u not in self.node_to_idx or v not in self.node_to_idx:
            return None

        i, j = self.node_to_idx[u], self.node_to_idx[v]

        if self.dist[i][j] == float("inf"):
            return None

        if i == j:
            return [u]

        if self.next_node[i][j] is None:
            return None

        path = [u]
        curr = i
        visited = set()

        while curr != j:
            if curr in visited:
                # Cycle detected
                return None
            visited.add(curr)
            curr = self.next_node[curr][j]
            if curr is None:
                return None
            path.append(self.idx_to_node[curr])

        return path

    def get_distance_dict(self, source: str) -> Dict[str, float]:
        """Convert row for source into a node_id -> distance dictionary."""
        if source not in self.node_to_idx:
            return {}
        i = self.node_to_idx[source]
        return {self.nodes[j]: self.dist[i][j] for j in range(len(self.nodes))}

    def to_matrix_dict(self) -> Dict[str, Any]:
        """Return distance matrix formatted as nested dict."""
        res: Dict[str, Dict[str, float]] = {}
        for u in self.nodes:
            i = self.node_to_idx[u]
            res[u] = {
                v: self.dist[i][self.node_to_idx[v]] for v in self.nodes
            }
        return res

    def to_dict(self) -> Dict[str, Any]:
        return {
            "matrix": self.to_matrix_dict(),
            "operations": self.operations,
            "has_negative_cycle": self.has_negative_cycle,
            "trace": self.trace,
        }


def floyd_warshall(
    graph: Graph,
    detect_negative_cycle: bool = True,
    trace_mode: bool = False,
    source_focus: Optional[str] = None,
) -> FloydWarshallResult:
    """Compute all-pairs shortest paths using the Floyd-Warshall algorithm.

    Time Complexity: O(|V|^3)
    Space Complexity: O(|V|^2)

    Args:
        graph: Graph instance.
        detect_negative_cycle: If True, checks diagonal for negative values.
        trace_mode: If True, records each step (k index, pair examined, distances, improvement).
        source_focus: Optional node ID to prioritize distance snapshots in trace.

    Returns:
        FloydWarshallResult with distance matrix, path reconstruction, op count, and optional trace.

    Raises:
        NegativeCycleException: If a negative-weight cycle is detected.
    """
    node_ids = list(graph.nodes.keys())
    n = len(node_ids)
    node_to_idx = {nid: i for i, nid in enumerate(node_ids)}

    # Initialize matrices
    dist: List[List[float]] = [[float("inf")] * n for _ in range(n)]
    next_node: List[List[Optional[int]]] = [[None] * n for _ in range(n)]

    # Self distance is 0
    for i in range(n):
        dist[i][i] = 0.0
        next_node[i][i] = i

    # Edge initialization
    for edge in graph.get_edges():
        u_idx = node_to_idx[edge.u]
        v_idx = node_to_idx[edge.v]
        # Multi-edge support: keep smallest latency if duplicate
        if edge.latency < dist[u_idx][v_idx]:
            dist[u_idx][v_idx] = edge.latency
            next_node[u_idx][v_idx] = v_idx

    operations = 0
    trace: List[Dict[str, Any]] = []

    # Floyd-Warshall Triple Nested Loop
    for k in range(n):
        k_node = node_ids[k]
        for i in range(n):
            u_node = node_ids[i]
            for j in range(n):
                v_node = node_ids[j]
                operations += 1  # 1 comparison / relaxation check

                dist_before = dist[i][j]
                improved = False

                # Check if path through k is shorter
                if dist[i][k] != float("inf") and dist[k][j] != float("inf"):
                    new_dist = dist[i][k] + dist[k][j]
                    if new_dist < dist[i][j]:
                        dist[i][j] = new_dist
                        next_node[i][j] = next_node[i][k]
                        improved = True

                if trace_mode:
                    is_focus = (source_focus is None) or (u_node == source_focus)
                    if improved or (is_focus and (dist[i][k] != float("inf") or dist[k][j] != float("inf"))):
                        explanation = (
                            f"k={k_node}: Relaxed ({u_node} -> {v_node}) via intermediate '{k_node}'. "
                            f"Distance improved from {dist_before if dist_before != float('inf') else '∞'} to {dist[i][j]:.1f} ms."
                            if improved else
                            f"k={k_node}: Evaluated ({u_node} -> {v_node}) through '{k_node}'. No improvement (current {dist_before:.1f} ms)."
                        )
                        focus_idx = node_to_idx.get(source_focus, i) if source_focus else i
                        row_distances = {
                            node_ids[idx]: (dist[focus_idx][idx] if dist[focus_idx][idx] != float("inf") else None)
                            for idx in range(n)
                        }
                        trace.append({
                            "k_index": k + 1,
                            "k_node": k_node,
                            "pair": {"u": u_node, "v": v_node},
                            "edge": {"u": u_node, "v": v_node, "weight": dist[i][j] if dist[i][j] != float("inf") else None},
                            "intermediate": k_node,
                            "dist_before": dist_before if dist_before != float("inf") else None,
                            "dist_after": dist[i][j] if dist[i][j] != float("inf") else None,
                            "improved": improved,
                            "distances": row_distances,
                            "explanation": explanation,
                        })

    # Negative cycle check: any diagonal entry < 0
    has_negative_cycle = False
    if detect_negative_cycle:
        for i in range(n):
            if dist[i][i] < -1e-9:
                has_negative_cycle = True
                raise NegativeCycleException(
                    f"Negative-weight cycle detected in graph involving node '{node_ids[i]}'."
                )

    return FloydWarshallResult(
        nodes=node_ids,
        node_to_idx=node_to_idx,
        dist_matrix=dist,
        next_matrix=next_node,
        operations=operations,
        has_negative_cycle=has_negative_cycle,
        trace=trace if trace_mode else None,
    )


def reconstruct_path(
    fw_result: FloydWarshallResult,
    source: str,
    target: str,
) -> Optional[List[str]]:
    """Helper function to reconstruct path using a precomputed FloydWarshallResult."""
    return fw_result.get_path(source, target)


def find_best_edge_server_fw(
    graph: Graph,
    user_region_id: str,
    fw_result: Optional[FloydWarshallResult] = None,
) -> Dict[str, Any]:
    """Find lowest-latency edge server from user_region_id using Floyd-Warshall.

    Args:
        graph: Graph instance.
        user_region_id: User region node ID.
        fw_result: Optional precomputed FloydWarshallResult to avoid recomputation.

    Returns:
        Dictionary with best_edge_id, latency, path, and operations.
    """
    if fw_result is None:
        fw_result = floyd_warshall(graph)

    edge_servers = graph.get_nodes_by_type("edge_server")
    best_edge_id: Optional[str] = None
    min_latency = float("inf")

    for es in edge_servers:
        d = fw_result.get_distance(user_region_id, es.id)
        if d < min_latency:
            min_latency = d
            best_edge_id = es.id

    best_path = fw_result.get_path(user_region_id, best_edge_id) if best_edge_id else None

    return {
        "user_region": user_region_id,
        "best_edge": best_edge_id,
        "latency": min_latency if min_latency != float("inf") else None,
        "path": best_path,
        "operations": fw_result.operations,
        "algorithm": "Floyd-Warshall",
    }
