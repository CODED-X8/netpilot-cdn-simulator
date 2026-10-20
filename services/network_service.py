"""Pure functional service layer for Mini CDN Simulator.

Encapsulates routing engines, max flow, fault simulation, what-if counterfactuals,
and metrics. All operations are logged to the structured SQLite EventStore.
Used by the Flask API, the dashboard, and the NetPilot Copilot agent.
"""

from typing import Dict, List, Optional, Any, Union, Tuple
import random
import time
import copy

from graph.network import Graph
from graph.generator import generate_cdn_topology
from routing.bellman_ford import find_best_edge_server_bf, bellman_ford
from routing.floyd_warshall import find_best_edge_server_fw, floyd_warshall
from routing.dijkstra import find_best_edge_server_dijkstra, dijkstra
from routing.max_flow import edmonds_karp, ford_fulkerson, compute_max_flow
from storage.event_store import get_event_store

# In-memory active topologies keyed by session_id
_ACTIVE_TOPOLOGIES: Dict[str, Dict[str, Any]] = {}
DEFAULT_SESSION_ID = "default"


def get_active_topology_entry(session_id: str = DEFAULT_SESSION_ID) -> Dict[str, Any]:
    """Retrieve session topology container, initializing default if absent."""
    if session_id not in _ACTIVE_TOPOLOGIES:
        _ACTIVE_TOPOLOGIES[session_id] = {
            "name": "Sample Hierarchical CDN",
            "graph": generate_cdn_topology(num_origins=1, num_edges=8, num_users=5, seed=42),
            "updated_at": time.time(),
        }
    return _ACTIVE_TOPOLOGIES[session_id]


def get_active_graph(session_id: str = DEFAULT_SESSION_ID) -> Graph:
    """Retrieve the current active Graph for the given session."""
    return get_active_topology_entry(session_id)["graph"]


def set_active_graph(graph: Graph, name: str = "Uploaded Topology", session_id: str = DEFAULT_SESSION_ID):
    """Set or replace the active Graph for the given session."""
    _ACTIVE_TOPOLOGIES[session_id] = {
        "name": name,
        "graph": graph,
        "updated_at": time.time(),
    }


def list_nodes(
    graph: Optional[Graph] = None,
    node_type: Optional[str] = None,
    session_id: str = DEFAULT_SESSION_ID,
) -> List[Dict[str, Any]]:
    """List all nodes in the graph with optional node_type filter."""
    g = graph or get_active_graph(session_id)
    nodes = g.get_nodes()
    if node_type:
        nodes = [n for n in nodes if n.node_type == node_type or n.metadata.get("tier") == node_type]
    return [n.to_dict() for n in nodes]


def get_metrics(
    graph: Optional[Graph] = None,
    session_id: str = DEFAULT_SESSION_ID,
    topology_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute structural metrics and health indicators of the network."""
    t0 = time.perf_counter()
    g = graph or get_active_graph(session_id)
    top_name = topology_name or get_active_topology_entry(session_id)["name"]

    node_types: Dict[str, int] = {}
    for node in g.get_nodes():
        t = node.metadata.get("tier") or node.node_type
        node_types[t] = node_types.get(t, 0) + 1

    edges = g.get_edges()
    edge_count = len(edges)
    avg_latency = (sum(e.latency for e in edges) / edge_count) if edge_count > 0 else 0.0
    total_capacity = sum(e.bandwidth_capacity for e in edges)

    compute_time_ms = (time.perf_counter() - t0) * 1000.0

    metrics = {
        "topology_name": top_name,
        "node_count": len(g),
        "edge_count": edge_count,
        "node_types": node_types,
        "average_latency_ms": round(avg_latency, 2),
        "total_bandwidth_capacity_mbps": round(total_capacity, 1),
    }

    return metrics


def shortest_path(
    source: str,
    algo: str = "bellman_ford",
    graph: Optional[Graph] = None,
    session_id: str = DEFAULT_SESSION_ID,
    topology_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute single-source shortest path from source region to nearest edge server."""
    t0 = time.perf_counter()
    g = graph or get_active_graph(session_id)
    top_name = topology_name or get_active_topology_entry(session_id)["name"]

    if not g.has_node(source):
        raise ValueError(f"Source node '{source}' does not exist in active topology.")

    algo_norm = algo.lower().strip()
    if algo_norm in ("bellman_ford", "bf"):
        result = find_best_edge_server_bf(g, source, early_stopping=False)
        complexity = "O(|V| * |E|)"
    elif algo_norm in ("floyd_warshall", "fw"):
        result = find_best_edge_server_fw(g, source)
        complexity = "O(|V|^3)"
    elif algo_norm in ("dijkstra", "dijk"):
        result = find_best_edge_server_dijkstra(g, source)
        complexity = "O((|V| + |E|) log |V|)"
    else:
        raise ValueError(f"Unknown routing algorithm '{algo}'. Must be 'bellman_ford', 'floyd_warshall', or 'dijkstra'.")

    t1 = time.perf_counter()
    exec_time_ms = (t1 - t0) * 1000.0

    path = result.get("path") or []
    path_edges = [{"from": path[i], "to": path[i + 1]} for i in range(len(path) - 1)]
    hops = max(0, len(path) - 1)

    payload = {
        "source": source,
        "best_edge": result.get("best_edge"),
        "latency": result.get("latency"),
        "hops": hops,
        "path": path,
        "path_edges": path_edges,
        "operations": result.get("operations", 0),
        "compute_time_ms": round(exec_time_ms, 4),
        "algorithm": result.get("algorithm", algo),
        "complexity": complexity,
        "topology_name": top_name,
    }

    # Log to Event Store
    get_event_store().log_event(
        event_type="route_computation",
        session_id=session_id,
        topology_name=top_name,
        inputs={"source": source, "algorithm": algo},
        results=payload,
        ops_count=payload["operations"],
        compute_time_ms=payload["compute_time_ms"],
    )

    return payload


def compare_algorithms(
    source: str,
    graph: Optional[Graph] = None,
    session_id: str = DEFAULT_SESSION_ID,
    topology_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute Bellman-Ford, Floyd-Warshall, and Dijkstra on the same source and cross-validate."""
    t0 = time.perf_counter()
    g = graph or get_active_graph(session_id)
    top_name = topology_name or get_active_topology_entry(session_id)["name"]

    if not g.has_node(source):
        raise ValueError(f"Source node '{source}' does not exist in active topology.")

    # 1. Bellman-Ford
    t_bf0 = time.perf_counter()
    bf_res = find_best_edge_server_bf(g, source, early_stopping=False)
    bf_time = (time.perf_counter() - t_bf0) * 1000.0

    # 2. Floyd-Warshall
    t_fw0 = time.perf_counter()
    fw_res = find_best_edge_server_fw(g, source)
    fw_time = (time.perf_counter() - t_fw0) * 1000.0

    # 3. Dijkstra
    t_dijk0 = time.perf_counter()
    dijk_res = find_best_edge_server_dijkstra(g, source)
    dijk_time = (time.perf_counter() - t_dijk0) * 1000.0

    bf_lat = bf_res.get("latency")
    fw_lat = fw_res.get("latency")
    dijk_lat = dijk_res.get("latency")

    matched_bf_fw = (bf_lat is not None and fw_lat is not None and abs(bf_lat - fw_lat) < 1e-4)
    three_way_matched = (
        matched_bf_fw
        and dijk_lat is not None
        and abs(bf_lat - dijk_lat) < 1e-4
        and bf_res.get("best_edge") == fw_res.get("best_edge") == dijk_res.get("best_edge")
    )

    path = bf_res.get("path") or dijk_res.get("path") or []
    path_edges = [{"from": path[i], "to": path[i + 1]} for i in range(len(path) - 1)]

    total_ops = bf_res.get("operations", 0) + fw_res.get("operations", 0) + dijk_res.get("operations", 0)
    total_time = (time.perf_counter() - t0) * 1000.0

    max_lat_diff = 0.0
    if bf_lat is not None and fw_lat is not None:
        max_lat_diff = max(max_lat_diff, abs(bf_lat - fw_lat))
    if bf_lat is not None and dijk_lat is not None:
        max_lat_diff = max(max_lat_diff, abs(bf_lat - dijk_lat))

    payload = {
        "source": source,
        "best_edge": bf_res.get("best_edge"),
        "latency": bf_lat,
        "path": path,
        "path_edges": path_edges,
        "hops": max(0, len(path) - 1),
        "bellman_ford": {
            "algorithm": "Bellman-Ford",
            "complexity": "O(|V| * |E|)",
            "best_edge": bf_res.get("best_edge"),
            "latency": bf_lat,
            "path": bf_res.get("path"),
            "operations": bf_res.get("operations", 0),
            "execution_time_ms": round(bf_time, 4),
        },
        "floyd_warshall": {
            "algorithm": "Floyd-Warshall",
            "complexity": "O(|V|^3)",
            "best_edge": fw_res.get("best_edge"),
            "latency": fw_lat,
            "path": fw_res.get("path"),
            "operations": fw_res.get("operations", 0),
            "execution_time_ms": round(fw_time, 4),
        },
        "dijkstra": {
            "algorithm": "Dijkstra",
            "complexity": "O((|V| + |E|) log |V|)",
            "best_edge": dijk_res.get("best_edge"),
            "latency": dijk_lat,
            "path": dijk_res.get("path"),
            "operations": dijk_res.get("operations", 0),
            "execution_time_ms": round(dijk_time, 4),
        },
        "agreement": {
            "matched": three_way_matched,
            "three_way_matched": three_way_matched,
            "best_edge_match": (bf_res.get("best_edge") == fw_res.get("best_edge") == dijk_res.get("best_edge")),
            "latency_diff": round(max_lat_diff, 4),
        },
        "topology_name": top_name,
    }

    # Log to Event Store
    get_event_store().log_event(
        event_type="algorithm_comparison",
        session_id=session_id,
        topology_name=top_name,
        inputs={"source": source},
        results=payload,
        ops_count=total_ops,
        compute_time_ms=total_time,
    )

    return payload


def kill_edge(
    edge_id: Optional[str] = None,
    u: Optional[str] = None,
    v: Optional[str] = None,
    graph: Optional[Graph] = None,
    session_id: str = DEFAULT_SESSION_ID,
    topology_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Sever a communication link in the active graph to simulate network failure."""
    t0 = time.perf_counter()
    g = graph or get_active_graph(session_id)
    top_name = topology_name or get_active_topology_entry(session_id)["name"]

    edges = g.get_edges()
    if not edges:
        raise ValueError("Cannot kill edge: graph has no links.")

    target_u = u
    target_v = v

    if edge_id:
        # Parse edge_id format e.g. "u->v" or "u<->v"
        sep = "<->" if "<->" in edge_id else "->"
        parts = edge_id.split(sep)
        if len(parts) == 2:
            target_u, target_v = parts[0].strip(), parts[1].strip()

    if target_u is None or target_v is None or not g.has_edge(target_u, target_v):
        # Pick a random edge if not explicitly provided or invalid
        chosen = random.choice(edges)
        target_u, target_v = chosen.u, chosen.v

    edge_obj = g.get_edge(target_u, target_v)
    latency = edge_obj.latency if edge_obj else 0.0

    # Cut link bidirectionally to represent physical severance
    g.remove_edge(target_u, target_v, bidirectional=True)
    compute_time_ms = (time.perf_counter() - t0) * 1000.0

    payload = {
        "status": "success",
        "killed_edge": {"u": target_u, "v": target_v, "latency": latency},
        "remaining_edges": g.edge_count(),
        "topology_name": top_name,
    }

    get_event_store().log_event(
        event_type="link_failure",
        session_id=session_id,
        topology_name=top_name,
        inputs={"edge_id": edge_id, "u": target_u, "v": target_v},
        results=payload,
        ops_count=1,
        compute_time_ms=compute_time_ms,
    )

    return payload


def reset_network(
    session_id: str = DEFAULT_SESSION_ID,
    topology_name: str = "Sample Hierarchical CDN",
) -> Dict[str, Any]:
    """Reset the session's active graph to baseline hierarchical CDN topology."""
    t0 = time.perf_counter()
    new_graph = generate_cdn_topology(num_origins=1, num_edges=8, num_users=5, seed=42)
    set_active_graph(new_graph, name=topology_name, session_id=session_id)
    compute_time_ms = (time.perf_counter() - t0) * 1000.0

    payload = {
        "status": "success",
        "message": f"Topology reset to baseline '{topology_name}'.",
        "node_count": len(new_graph),
        "edge_count": new_graph.edge_count(),
        "topology_name": topology_name,
    }

    get_event_store().log_event(
        event_type="network_reset",
        session_id=session_id,
        topology_name=topology_name,
        inputs={},
        results=payload,
        ops_count=1,
        compute_time_ms=compute_time_ms,
    )

    return payload


def what_if(
    remove_nodes: Optional[List[str]] = None,
    remove_edges: Optional[List[Union[str, Tuple[str, str]]]] = None,
    source: Optional[str] = None,
    graph: Optional[Graph] = None,
    session_id: str = DEFAULT_SESSION_ID,
    topology_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute counterfactual what-if simulation on a strict CLONE of the graph."""
    t0 = time.perf_counter()
    live_graph = graph or get_active_graph(session_id)
    top_name = topology_name or get_active_topology_entry(session_id)["name"]

    # 1. Deep clone the graph so live network remains untouched
    sim_graph = live_graph.clone()

    nodes_to_remove = remove_nodes or []
    edges_to_remove = remove_edges or []

    # 2. Determine target source for evaluation
    eval_source = source
    if not eval_source:
        user_nodes = [n.id for n in live_graph.get_nodes_by_type("user_region")]
        eval_source = user_nodes[0] if user_nodes else list(live_graph.nodes.keys())[0]

    # Baseline computation before mutations
    before_res = find_best_edge_server_bf(live_graph, eval_source, early_stopping=False)

    # 3. Apply counterfactual removals on sim_graph
    removed_nodes_actual = []
    for nid in nodes_to_remove:
        if sim_graph.has_node(nid):
            # Remove incident edges first
            incident = []
            for u in list(sim_graph.adj.keys()):
                for v in list(sim_graph.adj[u].keys()):
                    if u == nid or v == nid:
                        incident.append((u, v))
            for u, v in incident:
                sim_graph.remove_edge(u, v)
            del sim_graph.nodes[nid]
            if nid in sim_graph.adj:
                del sim_graph.adj[nid]
            removed_nodes_actual.append(nid)

    removed_edges_actual = []
    for item in edges_to_remove:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            u, v = str(item[0]), str(item[1])
        else:
            sep = "<->" if "<->" in str(item) else "->"
            parts = str(item).split(sep)
            if len(parts) == 2:
                u, v = parts[0].strip(), parts[1].strip()
            else:
                continue
        if sim_graph.has_edge(u, v):
            sim_graph.remove_edge(u, v, bidirectional=True)
            removed_edges_actual.append(f"{u}<->{v}")

    # After computation
    if sim_graph.has_node(eval_source):
        after_res = find_best_edge_server_bf(sim_graph, eval_source, early_stopping=False)
    else:
        after_res = {"best_edge": None, "latency": None, "path": [], "operations": 0}

    compute_time_ms = (time.perf_counter() - t0) * 1000.0
    total_ops = before_res.get("operations", 0) + after_res.get("operations", 0)

    before_lat = before_res.get("latency")
    after_lat = after_res.get("latency")
    latency_delta = None
    if before_lat is not None and after_lat is not None:
        latency_delta = round(after_lat - before_lat, 2)

    payload = {
        "source": eval_source,
        "removed_nodes": removed_nodes_actual,
        "removed_edges": removed_edges_actual,
        "before": {
            "best_edge": before_res.get("best_edge"),
            "latency": before_lat,
            "hops": max(0, len(before_res.get("path") or []) - 1),
            "path": before_res.get("path"),
        },
        "after": {
            "best_edge": after_res.get("best_edge"),
            "latency": after_lat,
            "hops": max(0, len(after_res.get("path") or []) - 1),
            "path": after_res.get("path"),
        },
        "latency_delta_ms": latency_delta,
        "is_severed": after_lat is None,
        "compute_time_ms": round(compute_time_ms, 4),
        "topology_name": top_name,
    }

    get_event_store().log_event(
        event_type="what_if_simulation",
        session_id=session_id,
        topology_name=top_name,
        inputs={
            "source": eval_source,
            "remove_nodes": nodes_to_remove,
            "remove_edges": [str(e) for e in edges_to_remove],
        },
        results=payload,
        ops_count=total_ops,
        compute_time_ms=compute_time_ms,
    )

    return payload


def max_flow(
    source: Optional[str] = None,
    sinks: Optional[Union[str, List[str]]] = None,
    algo: str = "edmonds_karp",
    graph: Optional[Graph] = None,
    session_id: str = DEFAULT_SESSION_ID,
    topology_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute maximum flow computation and log structured event."""
    t0 = time.perf_counter()
    g = graph or get_active_graph(session_id)
    top_name = topology_name or get_active_topology_entry(session_id)["name"]

    # Default source: first origin server
    src = source
    if not src:
        origins = g.get_nodes_by_type("origin")
        src = origins[0].id if origins else list(g.nodes.keys())[0]

    # Default sinks: all edge servers
    snk_list: List[str] = []
    if sinks:
        snk_list = [sinks] if isinstance(sinks, str) else list(sinks)
    else:
        edge_servers = g.get_nodes_by_type("edge_server")
        snk_list = [e.id for e in edge_servers] if edge_servers else [list(g.nodes.keys())[-1]]

    result = compute_max_flow(g, source=src, sinks=snk_list, algorithm=algo)
    payload = result.to_dict()
    payload["topology_name"] = top_name

    get_event_store().log_event(
        event_type="max_flow_computation",
        session_id=session_id,
        topology_name=top_name,
        inputs={"source": src, "sinks": snk_list, "algorithm": algo},
        results=payload,
        ops_count=result.operations,
        compute_time_ms=result.compute_time_ms,
    )

    return payload


def find_bottleneck(
    source: Optional[str] = None,
    sinks: Optional[Union[str, List[str]]] = None,
    graph: Optional[Graph] = None,
    session_id: str = DEFAULT_SESSION_ID,
    topology_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Locate network capacity bottlenecks via minimum cut analysis."""
    flow_res = max_flow(source=source, sinks=sinks, algo="edmonds_karp", graph=graph, session_id=session_id, topology_name=topology_name)
    top_name = topology_name or get_active_topology_entry(session_id)["name"]

    min_cut_edges = flow_res["min_cut_edges"]
    max_flow_val = flow_res["max_flow"]

    bottlenecks = []
    g = graph or get_active_graph(session_id)
    for item in min_cut_edges:
        u, v = item["u"], item["v"]
        edge = g.get_edge(u, v)
        cap = edge.bandwidth_capacity if edge else 0.0
        bottlenecks.append({
            "u": u,
            "v": v,
            "capacity_mbps": cap,
            "edge_id": f"{u}->{v}",
        })

    payload = {
        "bottleneck_edges": bottlenecks,
        "bottleneck_count": len(bottlenecks),
        "total_bottleneck_capacity": flow_res["min_cut_capacity"],
        "max_flow": max_flow_val,
        "source": flow_res["source"],
        "sinks": flow_res["sinks"],
        "topology_name": top_name,
    }

    get_event_store().log_event(
        event_type="bottleneck_analysis",
        session_id=session_id,
        topology_name=top_name,
        inputs={"source": flow_res["source"], "sinks": flow_res["sinks"]},
        results=payload,
        ops_count=flow_res["operations"],
        compute_time_ms=flow_res["compute_time_ms"],
    )

    return payload


def explain_route_trace(
    source: str,
    algo: str = "bellman_ford",
    graph: Optional[Graph] = None,
    session_id: str = DEFAULT_SESSION_ID,
) -> Dict[str, Any]:
    """Execute Bellman-Ford or Floyd-Warshall with step-by-step tracing for explainability.

    Limits execution to topologies of at most 30 nodes.
    """
    g = graph or get_active_graph(session_id)

    if len(g) > 30:
        raise ValueError(
            f"Step-through visualizer is limited to topologies with at most 30 nodes (current topology has {len(g)} nodes)."
        )

    if not g.has_node(source):
        raise ValueError(f"Source node '{source}' does not exist in active topology.")

    algo_norm = algo.lower().strip()
    if algo_norm in ("bellman_ford", "bf"):
        bf_res = bellman_ford(g, source, detect_negative_cycle=True, early_stopping=False, trace_mode=True)
        edge_servers = g.get_nodes_by_type("edge_server")
        best_edge_id = None
        min_lat = float("inf")
        for es in edge_servers:
            dist = bf_res.distances.get(es.id, float("inf"))
            if dist < min_lat:
                min_lat = dist
                best_edge_id = es.id
        return {
            "algorithm": "Bellman-Ford",
            "source": source,
            "best_edge": best_edge_id,
            "latency": min_lat if min_lat != float("inf") else None,
            "path": bf_res.get_path(best_edge_id) if best_edge_id else None,
            "node_count": len(g),
            "edge_count": g.edge_count(),
            "total_steps": len(bf_res.trace),
            "steps": bf_res.trace,
            "final_distances": {k: (v if v != float("inf") else None) for k, v in bf_res.distances.items()},
        }
    elif algo_norm in ("floyd_warshall", "fw"):
        fw_res = floyd_warshall(g, detect_negative_cycle=True, trace_mode=True, source_focus=source)
        edge_servers = g.get_nodes_by_type("edge_server")
        best_edge_id = None
        min_lat = float("inf")
        for es in edge_servers:
            dist = fw_res.get_distance(source, es.id)
            if dist < min_lat:
                min_lat = dist
                best_edge_id = es.id
        return {
            "algorithm": "Floyd-Warshall",
            "source": source,
            "best_edge": best_edge_id,
            "latency": min_lat if min_lat != float("inf") else None,
            "path": fw_res.get_path(source, best_edge_id) if best_edge_id else None,
            "node_count": len(g),
            "edge_count": g.edge_count(),
            "total_steps": len(fw_res.trace),
            "steps": fw_res.trace,
            "final_distances": {k: (v if v != float("inf") else None) for k, v in fw_res.get_distance_dict(source).items()},
        }
    else:
        raise ValueError(f"Trace mode is supported for 'bellman_ford' and 'floyd_warshall' (got '{algo}').")

