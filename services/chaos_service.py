"""Chaos Mode Service for Mini CDN Routing Simulator (Milestone X3).

Injects recurring random link failures at a configurable interval (min 5 seconds)
on the user's session topology, recomputes the active shortest-path route,
logs structured failure events to EventStore, triggers automated postmortem generation,
and supports manual stop with topology restoration or automatic reset after M failures.
"""

import random
import time
from typing import Dict, Any, Optional, List

from storage.event_store import get_event_store
import services.network_service as net_service
from services.postmortem_service import generate_postmortem


# In-memory session tracking for active chaos routines
_chaos_sessions: Dict[str, Dict[str, Any]] = {}


def start_chaos(
    session_id: str = net_service.DEFAULT_SESSION_ID,
    interval_seconds: int = 5,
    max_failures: int = 5,
    source: Optional[str] = None,
    algo: str = "bellman_ford",
) -> Dict[str, Any]:
    """Initialize and activate a Chaos Mode loop on the active session topology.

    Args:
        session_id: Unique session identifier.
        interval_seconds: Time between link failures (N >= 5 enforced).
        max_failures: Maximum link failures before auto-reset (M >= 1).
        source: Optional user region node to monitor. If None, picks the first user node.
        algo: Routing algorithm to recompute routes with ('bellman_ford', 'dijkstra', 'floyd_warshall').

    Returns:
        Session status dictionary.

    Raises:
        ValueError: If interval_seconds < 5 or max_failures < 1.
    """
    if interval_seconds < 5:
        raise ValueError(
            f"Chaos interval must be at least 5 seconds (requested {interval_seconds}s). "
            f"Configured interval cannot be less than 5s."
        )

    if max_failures < 1:
        raise ValueError(
            f"Maximum failures before auto-reset must be at least 1 (requested {max_failures})."
        )

    g = net_service.get_active_graph(session_id)
    if not source or not g.has_node(source):
        user_nodes = g.get_nodes_by_type("user_region")
        if user_nodes:
            source = user_nodes[0].id
        else:
            nodes = list(g.get_nodes().keys())
            source = nodes[0] if nodes else "unknown"

    state = {
        "session_id": session_id,
        "is_active": True,
        "interval_seconds": int(interval_seconds),
        "max_failures": int(max_failures),
        "failure_count": 0,
        "source": source,
        "algo": algo.lower().strip(),
        "history": [],
        "last_postmortem": None,
        "started_at": time.time(),
    }

    _chaos_sessions[session_id] = state

    top_entry = net_service.get_active_topology_entry(session_id)
    top_name = top_entry["name"] if top_entry else "Active Topology"

    get_event_store().log_event(
        event_type="chaos_started",
        session_id=session_id,
        topology_name=top_name,
        inputs={
            "interval_seconds": interval_seconds,
            "max_failures": max_failures,
            "source": source,
            "algo": algo,
        },
        results={"status": "started", "message": f"Chaos mode started with N={interval_seconds}s, M={max_failures}"},
        ops_count=0,
        compute_time_ms=0.1,
    )

    return {
        "status": "started",
        "session_id": session_id,
        "interval_seconds": interval_seconds,
        "max_failures": max_failures,
        "source": source,
        "algorithm": algo,
        "is_active": True,
    }


def chaos_tick(session_id: str = net_service.DEFAULT_SESSION_ID) -> Dict[str, Any]:
    """Execute one chaos tick: sever a random link, recompute active route, log event, and generate postmortem.

    If failure_count reaches max_failures, triggers automatic topology reset.
    """
    state = _chaos_sessions.get(session_id)
    if not state or not state.get("is_active"):
        raise ValueError("Chaos mode is not currently active for this session.")

    g = net_service.get_active_graph(session_id)
    source = state.get("source")
    algo = state.get("algo", "bellman_ford")

    edges = g.get_edges()
    if not edges:
        # No more links left to sever, auto-reset immediately
        net_service.reset_network(session_id)
        state["is_active"] = False
        return {
            "status": "completed",
            "message": "All links severed; network auto-reset to baseline.",
            "auto_reset_triggered": True,
            "is_active": False,
        }

    # 1. Measure active route BEFORE the failure
    try:
        before_res = net_service.shortest_path(source=source, algo=algo, session_id=session_id)
        before_lat = before_res.get("latency")
        before_path = before_res.get("path") or []
        before_edge = before_res.get("best_edge")
        before_hops = len(before_path) - 1 if len(before_path) > 1 else 0
    except Exception:
        before_lat, before_path, before_edge, before_hops = None, [], None, 0

    # 2. Inject random link failure
    chosen = random.choice(edges)
    u, v, latency = chosen.u, chosen.v, chosen.latency
    g.remove_edge(u, v, bidirectional=True)

    # 3. Recompute active route AFTER the failure
    try:
        after_res = net_service.shortest_path(source=source, algo=algo, session_id=session_id)
        after_lat = after_res.get("latency")
        after_path = after_res.get("path") or []
        after_edge = after_res.get("best_edge")
        after_hops = len(after_path) - 1 if len(after_path) > 1 else 0
        reachable = after_lat is not None and after_lat != float("inf")
    except Exception:
        after_lat, after_path, after_edge, after_hops, reachable = None, [], None, 0, False

    delta_ms = None
    if before_lat is not None and after_lat is not None:
        delta_ms = round(after_lat - before_lat, 2)

    state["failure_count"] += 1
    current_count = state["failure_count"]
    max_failures = state["max_failures"]

    # 4. Log structured failure event
    top_entry = net_service.get_active_topology_entry(session_id)
    top_name = top_entry["name"] if top_entry else "Active Topology"

    payload = {
        "status": "success",
        "killed_edge": {"u": u, "v": v, "latency": latency},
        "remaining_edges": g.edge_count(),
        "before": {
            "path": before_path,
            "latency": before_lat,
            "best_edge": before_edge,
            "hops": before_hops,
        },
        "after": {
            "path": after_path,
            "latency": after_lat,
            "best_edge": after_edge,
            "hops": after_hops,
            "reachable": reachable,
        },
        "latency_delta_ms": delta_ms,
        "failure_index": current_count,
        "max_failures": max_failures,
        "interval_seconds": state["interval_seconds"],
    }

    evt = get_event_store().log_event(
        event_type="failure_simulation",
        session_id=session_id,
        topology_name=top_name,
        inputs={"u": u, "v": v, "source": source, "chaos_mode": True, "edge_id": f"{u}<->{v}"},
        results=payload,
        ops_count=1,
        compute_time_ms=0.8,
    )

    # 5. Generate automated incident postmortem
    postmortem = generate_postmortem(event_id=evt.id, session_id=session_id)
    state["last_postmortem"] = postmortem

    state["history"].append({
        "event_id": evt.id,
        "timestamp": evt.timestamp,
        "killed_edge": f"{u} <-> {v}",
        "latency_delta_ms": delta_ms,
        "after_latency": after_lat,
        "reachable": reachable,
    })

    # 6. Check for auto-reset condition after M failures
    auto_reset_triggered = False
    if current_count >= max_failures:
        auto_reset_triggered = True
        state["is_active"] = False
        net_service.reset_network(session_id)
        get_event_store().log_event(
            event_type="chaos_auto_reset",
            session_id=session_id,
            topology_name=top_name,
            inputs={"failures_reached": current_count, "max_failures": max_failures},
            results={
                "status": "auto_reset",
                "message": f"Auto-reset triggered after reaching {current_count} of {max_failures} failures.",
            },
            ops_count=0,
            compute_time_ms=0.5,
        )

    return {
        "status": "success",
        "tick_number": current_count,
        "max_failures": max_failures,
        "interval_seconds": state["interval_seconds"],
        "is_active": state["is_active"],
        "auto_reset_triggered": auto_reset_triggered,
        "killed_edge": {"u": u, "v": v, "latency": latency},
        "remaining_edges": g.edge_count(),
        "source": source,
        "before": payload["before"],
        "after": payload["after"],
        "latency_delta_ms": delta_ms,
        "event_id": evt.id,
        "postmortem": postmortem,
    }


def stop_chaos(
    session_id: str = net_service.DEFAULT_SESSION_ID,
    restore_topology: bool = True,
) -> Dict[str, Any]:
    """Stop the Chaos Mode loop and optionally restore the topology to baseline."""
    state = _chaos_sessions.get(session_id)
    was_active = state.get("is_active", False) if state else False

    if state:
        state["is_active"] = False

    if restore_topology:
        net_service.reset_network(session_id)

    top_entry = net_service.get_active_topology_entry(session_id)
    top_name = top_entry["name"] if top_entry else "Active Topology"

    get_event_store().log_event(
        event_type="chaos_stopped",
        session_id=session_id,
        topology_name=top_name,
        inputs={"restore_topology": restore_topology},
        results={"status": "stopped", "was_active": was_active},
        ops_count=0,
        compute_time_ms=0.2,
    )

    return {
        "status": "stopped",
        "session_id": session_id,
        "is_active": False,
        "topology_restored": restore_topology,
        "failures_incurred": state.get("failure_count", 0) if state else 0,
    }


def get_chaos_status(session_id: str = net_service.DEFAULT_SESSION_ID) -> Dict[str, Any]:
    """Get current Chaos Mode state for the given session."""
    state = _chaos_sessions.get(session_id)
    if not state:
        return {
            "session_id": session_id,
            "is_active": False,
            "failure_count": 0,
            "max_failures": 5,
            "interval_seconds": 5,
            "last_postmortem": None,
            "history": [],
        }

    return {
        "session_id": session_id,
        "is_active": state.get("is_active", False),
        "failure_count": state.get("failure_count", 0),
        "max_failures": state.get("max_failures", 5),
        "interval_seconds": state.get("interval_seconds", 5),
        "source": state.get("source"),
        "algo": state.get("algo"),
        "last_postmortem": state.get("last_postmortem"),
        "history": state.get("history", []),
    }


def reset_chaos_state(session_id: Optional[str] = None) -> None:
    """Clear in-memory chaos state (useful for test isolation)."""
    global _chaos_sessions
    if session_id:
        _chaos_sessions.pop(session_id, None)
    else:
        _chaos_sessions.clear()
