"""Propose, Simulate, Verify Mitigation Engine (Milestone M7).

Generates candidate topology changes, simulates them on isolated graph copies,
discards invalid proposals, and deterministically ranks them by empirical metric delta.
"""

import json
from typing import Dict, List, Any, Optional

import services.network_service as net_service
from routing.max_flow import edmonds_karp
from routing.bellman_ford import bellman_ford
from storage.event_store import get_event_store


def _compute_graph_metrics(graph) -> Dict[str, float]:
    """Compute baseline or simulated graph metrics."""
    origins = [n for n, d in graph.nodes.items() if d.node_type == "origin"]
    edge_servers = [n for n, d in graph.nodes.items() if d.node_type == "edge_server"]
    user_regions = [n for n, d in graph.nodes.items() if d.node_type == "user_region"]

    origin_id = origins[0] if origins else list(graph.nodes.keys())[0]

    # 1. Max throughput and min-cut capacity from origin to edge servers
    try:
        flow_res = edmonds_karp(graph, source=origin_id, sinks=edge_servers)
        max_flow_val = flow_res.max_flow
        min_cut_cap = flow_res.min_cut_capacity
        min_cut_count = len(flow_res.min_cut_edges)
    except Exception:
        max_flow_val = 0.0
        min_cut_cap = 0.0
        min_cut_count = 0

    # 3. Average latency from user regions to nearest edge server
    latencies = []
    for u in user_regions:
        try:
            bf = bellman_ford(graph, source=u)
            best_lat = float("inf")
            for e in edge_servers:
                dist = bf["distances"].get(e, float("inf"))
                if dist < best_lat:
                    best_lat = dist
            if best_lat != float("inf"):
                latencies.append(best_lat)
        except Exception:
            pass

    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

    return {
        "max_flow": max_flow_val,
        "min_cut_capacity": min_cut_cap,
        "min_cut_count": min_cut_count,
        "average_latency": avg_latency,
    }


def get_default_candidates_for_goal(goal: str, graph) -> List[Dict[str, Any]]:
    """Generate intelligent rule-based candidates if LLM is offline or not supplied."""
    origins = [n for n, d in graph.nodes.items() if d.node_type == "origin"]
    edge_servers = [n for n, d in graph.nodes.items() if d.node_type == "edge_server"]
    user_regions = [n for n, d in graph.nodes.items() if d.node_type == "user_region"]

    origin = origins[0] if origins else "origin_1"
    target_edge = edge_servers[0] if edge_servers else "edge_1"
    user = user_regions[0] if user_regions else "user_1"

    g_lower = goal.lower()
    if "latency" in g_lower:
        return [
            {
                "action": "add_edge",
                "target": f"{user}<->{target_edge}",
                "u": user,
                "v": target_edge,
                "value": 8.0,
                "bandwidth_capacity": 500.0,
                "rationale": "Direct low-latency link bypassing intermediate transit hops.",
            },
            {
                "action": "increase_capacity",
                "target": f"{origin}<->{target_edge}",
                "u": origin,
                "v": target_edge,
                "value": 800.0,
                "rationale": "Expand core link capacity to minimize queuing delays.",
            },
            {
                "action": "add_edge",
                "target": f"{user}<->{origin}",
                "u": user,
                "v": origin,
                "value": 15.0,
                "bandwidth_capacity": 400.0,
                "rationale": "Emergency direct trunk to origin server.",
            },
        ]
    elif "bottleneck" in g_lower or "cut" in g_lower:
        return [
            {
                "action": "increase_capacity",
                "target": f"{origin}<->{target_edge}",
                "u": origin,
                "v": target_edge,
                "value": 1000.0,
                "rationale": "Widen saturated backbone link on min-cut boundary.",
            },
            {
                "action": "add_edge",
                "target": f"{origin}<->transit_1" if "transit_1" in graph.nodes else f"{origin}<->{edge_servers[-1]}",
                "u": origin,
                "v": "transit_1" if "transit_1" in graph.nodes else edge_servers[-1],
                "value": 12.0,
                "bandwidth_capacity": 600.0,
                "rationale": "Add parallel un-congested feeder link to divert bottleneck traffic.",
            },
            {
                "action": "increase_capacity",
                "target": "user_1<->edge_1",
                "u": "user_1",
                "v": "edge_1",
                "value": 500.0,
                "rationale": "Boost user-access link capacity.",
            },
        ]
    else:  # throughput / max flow
        return [
            {
                "action": "increase_capacity",
                "target": f"{origin}<->{target_edge}",
                "u": origin,
                "v": target_edge,
                "value": 1200.0,
                "rationale": "Increase primary trunk capacity to 1200 Mbps.",
            },
            {
                "action": "add_edge",
                "target": f"{origin}<->{edge_servers[-1]}",
                "u": origin,
                "v": edge_servers[-1],
                "value": 14.0,
                "bandwidth_capacity": 800.0,
                "rationale": "Deploy secondary direct distribution line to edge POP.",
            },
            {
                "action": "increase_capacity",
                "target": "transit_1<->edge_1" if "transit_1" in graph.nodes else f"{user}<->{target_edge}",
                "u": "transit_1" if "transit_1" in graph.nodes else user,
                "v": "edge_1" if "transit_1" in graph.nodes else target_edge,
                "value": 600.0,
                "rationale": "Expand intermediate regional bandwidth.",
            },
        ]


def propose_and_simulate_mitigations(
    goal: str,
    session_id: str = "default",
    candidates: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Propose up to 3 candidate mitigations, simulate each on a graph copy,

    discard invalid proposals, and deterministically rank by measured metrics.
    """
    graph = net_service.get_active_graph(session_id)
    baseline_metrics = _compute_graph_metrics(graph)

    # 1. Obtain candidates (custom or rule-based fallback)
    raw_candidates = candidates if candidates is not None else get_default_candidates_for_goal(goal, graph)

    valid_simulations = []
    discarded = []

    # 2. Simulate each candidate on an ISOLATED graph copy
    for idx, cand in enumerate(raw_candidates):
        action = cand.get("action")
        target = cand.get("target", "")
        val = cand.get("value", 0.0)
        u = cand.get("u")
        v = cand.get("v")

        # Resolve u and v from target if needed
        if (not u or not v) and "<->" in target:
            parts = target.split("<->")
            u, v = parts[0].strip(), parts[1].strip()

        # Validation checks
        if action not in ("add_edge", "increase_capacity", "remove_edge"):
            discarded.append({"candidate": cand, "reason": f"Unsupported action '{action}'"})
            continue

        if not u or not v:
            discarded.append({"candidate": cand, "reason": "Missing source/target node identifiers"})
            continue

        if u not in graph.nodes or v not in graph.nodes:
            discarded.append({"candidate": cand, "reason": f"Node '{u}' or '{v}' does not exist in graph"})
            continue

        if action in ("add_edge", "increase_capacity") and val <= 0:
            discarded.append({"candidate": cand, "reason": "Value (latency/capacity) must be positive"})
            continue

        # Create isolated copy
        sim_graph = graph.copy()

        # Apply change to copy
        try:
            if action == "add_edge":
                cap = cand.get("bandwidth_capacity", 500.0)
                sim_graph.add_edge(u, v, latency=val, bandwidth_capacity=cap, bidirectional=True)
            elif action == "increase_capacity":
                # Increase capacity in both directions if present
                found = False
                for edge in sim_graph.edges:
                    if (edge.u == u and edge.v == v) or (edge.u == v and edge.v == u):
                        edge.bandwidth_capacity = val
                        found = True
                if not found:
                    sim_graph.add_edge(u, v, latency=15.0, bandwidth_capacity=val, bidirectional=True)
            elif action == "remove_edge":
                sim_graph.remove_edge(u, v)
                if sim_graph.has_edge(v, u):
                    sim_graph.remove_edge(v, u)

            # Measure metrics on simulated graph copy
            sim_metrics = _compute_graph_metrics(sim_graph)

            delta_max_flow = round(sim_metrics["max_flow"] - baseline_metrics["max_flow"], 2)
            delta_avg_latency = round(sim_metrics["average_latency"] - baseline_metrics["average_latency"], 2)
            delta_bottleneck_cap = round(sim_metrics["min_cut_capacity"] - baseline_metrics["min_cut_capacity"], 2)

            valid_simulations.append({
                "candidate_id": f"cand_{idx + 1}",
                "action": action,
                "target": f"{u}<->{v}",
                "u": u,
                "v": v,
                "proposed_value": val,
                "rationale": cand.get("rationale", ""),
                "baseline_metrics": baseline_metrics,
                "simulated_metrics": sim_metrics,
                "measured_impact": {
                    "delta_max_flow_mbps": delta_max_flow,
                    "delta_avg_latency_ms": delta_avg_latency,
                    "delta_bottleneck_capacity_mbps": delta_bottleneck_cap,
                },
            })

        except Exception as exc:
            discarded.append({"candidate": cand, "reason": f"Simulation runtime error: {str(exc)}"})

    # 3. Deterministic Ranking based on goal
    g_lower = goal.lower()
    if "latency" in g_lower or "delay" in g_lower:
        # Minimize latency -> sort by delta_avg_latency ascending (most negative delta is best)
        valid_simulations.sort(key=lambda c: c["measured_impact"]["delta_avg_latency_ms"])
    elif "bottleneck" in g_lower or "cut" in g_lower:
        # Resolve bottleneck -> sort by delta_bottleneck_capacity descending
        valid_simulations.sort(key=lambda c: c["measured_impact"]["delta_bottleneck_capacity_mbps"], reverse=True)
    else:
        # Maximize throughput -> sort by delta_max_flow descending
        valid_simulations.sort(key=lambda c: c["measured_impact"]["delta_max_flow_mbps"], reverse=True)

    # Assign rank order
    for r, item in enumerate(valid_simulations, 1):
        item["rank"] = r

    return {
        "status": "success",
        "goal": goal,
        "baseline_metrics": baseline_metrics,
        "ranked_candidates": valid_simulations,
        "discarded_candidates": discarded,
    }


def apply_mitigation(
    candidate: Dict[str, Any],
    session_id: str = "default",
    confirmed: bool = False,
) -> Dict[str, Any]:
    """Apply a validated mitigation candidate to the active network graph.

    Requires explicit user confirmation (confirmed=True).
    """
    if not confirmed:
        return {
            "status": "confirmation_required",
            "message": "Applying mitigation alters the live network topology and requires explicit user confirmation.",
            "candidate": candidate,
        }

    action = candidate.get("action")
    u = candidate.get("u")
    v = candidate.get("v")
    val = candidate.get("proposed_value", 0.0)

    if not action or not u or not v:
        return {"error": "Invalid candidate payload. Missing action, u, or v."}

    graph = net_service.get_active_graph(session_id)
    top_name = net_service.get_active_topology_entry(session_id)["name"]

    if action == "add_edge":
        cap = candidate.get("bandwidth_capacity", 500.0)
        graph.add_edge(u, v, latency=val, bandwidth_capacity=cap, bidirectional=True)
    elif action == "increase_capacity":
        found = False
        for edge in graph.edges:
            if (edge.u == u and edge.v == v) or (edge.u == v and edge.v == u):
                edge.bandwidth_capacity = val
                found = True
        if not found:
            graph.add_edge(u, v, latency=15.0, bandwidth_capacity=val, bidirectional=True)
    elif action == "remove_edge":
        graph.remove_edge(u, v)
        if graph.has_edge(v, u):
            graph.remove_edge(v, u)

    # Log to event store
    es = get_event_store()
    event = es.log_event(
        event_type="apply_mitigation",
        session_id=session_id,
        topology_name=top_name,
        inputs={"action": action, "u": u, "v": v, "value": val},
        results={"status": "applied", "candidate": candidate},
    )

    return {
        "status": "success",
        "message": f"Successfully applied mitigation: {action} on {u}<->{v}",
        "event_id": event.id,
        "updated_metrics": _compute_graph_metrics(graph),
    }
