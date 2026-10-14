"""Max Flow algorithms from scratch for Mini CDN Simulator.

Implements:
1. Edmonds-Karp (BFS augmenting paths)
2. Ford-Fulkerson (DFS augmenting paths)
3. Support for single source (origin) and multiple sinks via virtual super-sink
4. Calculation of max flow, per-edge flow, augmentation counts, operations count,
   compute time, and the min-cut edge set (edges from source-reachable set to the rest).
"""

from typing import Dict, List, Optional, Set, Tuple, Any, Union
import time
from collections import deque
from graph.network import Graph


class MaxFlowResult:
    """Encapsulates the output of a max flow computation."""

    def __init__(
        self,
        max_flow: float,
        edge_flows: Dict[Tuple[str, str], float],
        augmenting_paths: int,
        operations: int,
        compute_time_ms: float,
        min_cut_edges: List[Tuple[str, str]],
        min_cut_capacity: float,
        source: str,
        sinks: List[str],
        algorithm: str,
        reachable_nodes: Optional[Set[str]] = None,
    ):
        self.max_flow = float(max_flow)
        self.edge_flows = edge_flows
        self.augmenting_paths = int(augmenting_paths)
        self.operations = int(operations)
        self.compute_time_ms = float(compute_time_ms)
        self.min_cut_edges = min_cut_edges
        self.min_cut_capacity = float(min_cut_capacity)
        self.source = source
        self.sinks = sinks
        self.algorithm = algorithm
        self.reachable_nodes = reachable_nodes or set()

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to JSON-serializable dictionary."""
        return {
            "max_flow": round(self.max_flow, 2),
            "edge_flows": {f"{u}->{v}": round(flow, 2) for (u, v), flow in self.edge_flows.items()},
            "augmenting_paths": self.augmenting_paths,
            "operations": self.operations,
            "compute_time_ms": round(self.compute_time_ms, 4),
            "min_cut_edges": [{"u": u, "v": v} for u, v in self.min_cut_edges],
            "min_cut_capacity": round(self.min_cut_capacity, 2),
            "source": self.source,
            "sinks": self.sinks,
            "algorithm": self.algorithm,
        }

    def __repr__(self) -> str:
        return (
            f"MaxFlowResult({self.algorithm}: max_flow={self.max_flow:.1f} Mbps, "
            f"augmentations={self.augmenting_paths}, ops={self.operations}, "
            f"time={self.compute_time_ms:.2f}ms, min_cut_edges={len(self.min_cut_edges)})"
        )


def _build_residual_network(
    graph: Graph,
    source: str,
    sinks: List[str],
) -> Tuple[Dict[str, Dict[str, float]], Dict[Tuple[str, str], float], str, bool]:
    """Construct residual capacity adjacency and map original capacities.

    If multiple sinks are provided, a virtual super-sink '__super_sink__' is created
    with infinite capacity directed links from each sink to the super-sink.
    """
    orig_cap: Dict[Tuple[str, str], float] = {}
    res_cap: Dict[str, Dict[str, float]] = {}

    # Initialize all nodes
    all_nodes = set(graph.nodes.keys())
    for u in all_nodes:
        res_cap[u] = {}

    # Add all directed edges with their bandwidth capacity
    for edge in graph.get_edges():
        u, v, cap = edge.u, edge.v, float(edge.bandwidth_capacity)
        orig_cap[(u, v)] = cap
        res_cap[u][v] = res_cap[u].get(v, 0.0) + cap
        if u not in res_cap[v]:
            res_cap[v][u] = 0.0

    has_super_sink = len(sinks) > 1
    if has_super_sink:
        super_sink = "__super_sink__"
        res_cap[super_sink] = {}
        for s in sinks:
            if s in res_cap:
                # High finite capacity exceeding any feasible network flow
                res_cap[s][super_sink] = float("inf")
                res_cap[super_sink][s] = 0.0
        target = super_sink
    else:
        target = sinks[0] if sinks else source

    return res_cap, orig_cap, target, has_super_sink


def _extract_flows_and_mincut(
    graph: Graph,
    res_cap: Dict[str, Dict[str, float]],
    orig_cap: Dict[Tuple[str, str], float],
    source: str,
    sinks: List[str],
    has_super_sink: bool,
    max_flow: float,
    augmenting_paths: int,
    operations: int,
    compute_time_ms: float,
    algo_name: str,
) -> MaxFlowResult:
    """Extract per-edge flows, reachable set S, and the minimum cut edge set."""
    # 1. Per-edge flows on original edges
    edge_flows: Dict[Tuple[str, str], float] = {}
    for (u, v), cap in orig_cap.items():
        rev_exists = (v, u) in orig_cap
        if rev_exists:
            # Handle anti-parallel / bidirectional links cleanly
            u_v_res = res_cap.get(u, {}).get(v, 0.0)
            v_u_res = res_cap.get(v, {}).get(u, 0.0)
            orig_uv = orig_cap[(u, v)]
            orig_vu = orig_cap[(v, u)]

            if u_v_res < orig_uv:
                edge_flows[(u, v)] = max(0.0, orig_uv - u_v_res)
            elif v_u_res < orig_vu:
                edge_flows[(u, v)] = 0.0
            else:
                edge_flows[(u, v)] = 0.0
        else:
            flow = max(0.0, cap - res_cap.get(u, {}).get(v, 0.0))
            edge_flows[(u, v)] = flow

    # 2. Find reachable set S in residual graph from source
    reachable: Set[str] = set()
    queue = deque([source])
    reachable.add(source)

    while queue:
        curr = queue.popleft()
        for neighbor, rem in res_cap.get(curr, {}).items():
            if rem > 1e-9 and neighbor not in reachable:
                # Do not traverse into virtual super-sink
                if neighbor != "__super_sink__":
                    reachable.add(neighbor)
                    queue.append(neighbor)

    # 3. Identify min-cut edges: original directed edges (u, v) where u in S, v not in S
    min_cut_edges: List[Tuple[str, str]] = []
    min_cut_cap = 0.0

    for (u, v), cap in orig_cap.items():
        if u in reachable and v not in reachable:
            min_cut_edges.append((u, v))
            min_cut_cap += cap

    return MaxFlowResult(
        max_flow=max_flow,
        edge_flows=edge_flows,
        augmenting_paths=augmenting_paths,
        operations=operations,
        compute_time_ms=compute_time_ms,
        min_cut_edges=min_cut_edges,
        min_cut_capacity=min_cut_cap,
        source=source,
        sinks=sinks,
        algorithm=algo_name,
        reachable_nodes=reachable,
    )


def edmonds_karp(
    graph: Graph,
    source: str,
    sinks: Union[str, List[str]],
) -> MaxFlowResult:
    """Compute maximum flow using Edmonds-Karp algorithm (BFS augmenting paths).

    Complexity: O(|V| * |E|^2)
    """
    t0 = time.perf_counter()
    sink_list = [sinks] if isinstance(sinks, str) else list(sinks)

    if not graph.has_node(source):
        raise ValueError(f"Source node '{source}' not found in graph.")
    for s in sink_list:
        if not graph.has_node(s):
            raise ValueError(f"Sink node '{s}' not found in graph.")

    res_cap, orig_cap, target, has_super_sink = _build_residual_network(graph, source, sink_list)

    max_flow = 0.0
    augmenting_paths = 0
    operations = 0

    while True:
        # BFS to find shortest path from source to target in residual graph
        parent: Dict[str, Tuple[Optional[str], float]] = {source: (None, float("inf"))}
        queue = deque([source])
        found = False

        while queue:
            operations += 1
            curr = queue.popleft()
            if curr == target:
                found = True
                break

            for neighbor, capacity in res_cap.get(curr, {}).items():
                operations += 1
                if capacity > 1e-9 and neighbor not in parent:
                    bottleneck = min(parent[curr][1], capacity)
                    parent[neighbor] = (curr, bottleneck)
                    queue.append(neighbor)

        if not found or target not in parent:
            break

        # Augment flow along found path
        push_flow = parent[target][1]
        curr = target
        while curr != source:
            prev = parent[curr][0]
            if prev is None:
                break
            res_cap[prev][curr] -= push_flow
            res_cap[curr][prev] += push_flow
            curr = prev

        max_flow += push_flow
        augmenting_paths += 1

    t1 = time.perf_counter()
    compute_time_ms = (t1 - t0) * 1000.0

    return _extract_flows_and_mincut(
        graph=graph,
        res_cap=res_cap,
        orig_cap=orig_cap,
        source=source,
        sinks=sink_list,
        has_super_sink=has_super_sink,
        max_flow=max_flow,
        augmenting_paths=augmenting_paths,
        operations=operations,
        compute_time_ms=compute_time_ms,
        algo_name="Edmonds-Karp (BFS)",
    )


def ford_fulkerson(
    graph: Graph,
    source: str,
    sinks: Union[str, List[str]],
) -> MaxFlowResult:
    """Compute maximum flow using Ford-Fulkerson algorithm (DFS augmenting paths).

    Complexity: O(|E| * |f*|) where f* is max flow.
    """
    t0 = time.perf_counter()
    sink_list = [sinks] if isinstance(sinks, str) else list(sinks)

    if not graph.has_node(source):
        raise ValueError(f"Source node '{source}' not found in graph.")
    for s in sink_list:
        if not graph.has_node(s):
            raise ValueError(f"Sink node '{s}' not found in graph.")

    res_cap, orig_cap, target, has_super_sink = _build_residual_network(graph, source, sink_list)

    max_flow = 0.0
    augmenting_paths = 0
    operations = 0

    while True:
        # DFS to find augmenting path
        visited: Set[str] = set()
        parent: Dict[str, str] = {}

        def dfs(u: str) -> Optional[float]:
            nonlocal operations
            operations += 1
            if u == target:
                return float("inf")

            visited.add(u)
            for v, rem in res_cap.get(u, {}).items():
                operations += 1
                if rem > 1e-9 and v not in visited:
                    parent[v] = u
                    pushed = dfs(v)
                    if pushed is not None:
                        return min(rem, pushed)
            return None

        flow_pushed = dfs(source)
        if flow_pushed is None or flow_pushed <= 1e-9:
            break

        # Augment flow along found DFS path
        curr = target
        while curr != source:
            prev = parent[curr]
            res_cap[prev][curr] -= flow_pushed
            res_cap[curr][prev] += flow_pushed
            curr = prev

        max_flow += flow_pushed
        augmenting_paths += 1

    t1 = time.perf_counter()
    compute_time_ms = (t1 - t0) * 1000.0

    return _extract_flows_and_mincut(
        graph=graph,
        res_cap=res_cap,
        orig_cap=orig_cap,
        source=source,
        sinks=sink_list,
        has_super_sink=has_super_sink,
        max_flow=max_flow,
        augmenting_paths=augmenting_paths,
        operations=operations,
        compute_time_ms=compute_time_ms,
        algo_name="Ford-Fulkerson (DFS)",
    )


def compute_max_flow(
    graph: Graph,
    source: str,
    sinks: Union[str, List[str]],
    algorithm: str = "edmonds_karp",
) -> MaxFlowResult:
    """Unified entry point for max flow computation."""
    algo = algorithm.lower().strip()
    if algo in ("edmonds_karp", "bfs", "ek"):
        return edmonds_karp(graph, source, sinks)
    elif algo in ("ford_fulkerson", "dfs", "ff"):
        return ford_fulkerson(graph, source, sinks)
    else:
        raise ValueError(f"Unknown max flow algorithm '{algorithm}'. Must be 'edmonds_karp' or 'ford_fulkerson'.")
