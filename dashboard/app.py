"""Flask Web Dashboard backend for Mini CDN Routing Simulator.

Integrates with the pure functional service layer (services/network_service.py)
and SQLite Event Store (storage/event_store.py).
Supports routing, cross-validation, fault simulation, max flow, what-if, and metrics.
"""

import os
import sys
import html
import csv
from typing import Dict, Any, Optional, List

from flask import Flask, render_template, jsonify, request, send_file

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from graph.network import Graph
import services.network_service as net_service
from storage.event_store import get_event_store

app = Flask(__name__)


def _get_session_id() -> str:
    """Extract or default session ID from request headers or query params."""
    return request.headers.get("X-Session-ID") or request.args.get("session_id") or "default"


def sanitize_text(text: Any, max_len: int = 100) -> str:
    """Sanitize and HTML-escape untrusted input text for UI safety."""
    if text is None:
        return ""
    # Strip non-printable/control characters
    cleaned = "".join(ch for ch in str(text) if ch.isprintable())
    # Truncate to max length
    cleaned = cleaned[:max_len]
    return html.escape(cleaned)


def format_graph_for_vis(g: Graph) -> Dict[str, Any]:
    """Transform Graph data structure into Vis.js network format with sanitized labels."""
    nodes = []
    for node in g.get_nodes():
        tier = node.metadata.get("tier", "edge")
        safe_label = sanitize_text(node.label)
        safe_id = sanitize_text(node.id)

        if node.node_type == "origin":
            shape = "diamond"
            color = {
                "background": "#ffb703",
                "border": "#fb8500",
                "highlight": {"background": "#ffe082", "border": "#d46b08"},
            }
            size = 26
            font = {"color": "#ffffff", "face": "system-ui", "size": 12, "strokeWidth": 2, "strokeColor": "#0f172a"}
        elif node.node_type == "edge_server":
            shape = "hexagon"
            color = {
                "background": "#00b4d8",
                "border": "#0077b6",
                "highlight": {"background": "#90e0ef", "border": "#03045e"},
            }
            size = 22
            font = {"color": "#ffffff", "face": "system-ui", "size": 12, "strokeWidth": 2, "strokeColor": "#0f172a"}
        elif tier == "transit" or node.node_type == "transit":
            shape = "dot"
            color = {
                "background": "#8b5cf6",
                "border": "#6d28d9",
                "highlight": {"background": "#c4b5fd", "border": "#5b21b6"},
            }
            size = 15
            font = {"color": "#cbd5e1", "face": "system-ui", "size": 10, "strokeWidth": 2, "strokeColor": "#0f172a"}
        else:  # user_region
            shape = "dot"
            color = {
                "background": "#10b981",
                "border": "#059669",
                "highlight": {"background": "#6ee7b7", "border": "#047857"},
            }
            size = 20
            font = {"color": "#ffffff", "face": "system-ui", "size": 12, "strokeWidth": 2, "strokeColor": "#0f172a"}

        nodes.append({
            "id": node.id,
            "label": safe_label,
            "node_type": node.node_type,
            "tier": tier,
            "shape": shape,
            "color": color,
            "size": size,
            "font": font,
            "title": f"<b>{safe_label}</b><br>ID: <code>{safe_id}</code><br>Type: {node.node_type}",
        })

    edges = []
    seen_pairs = set()
    for edge in g.get_edges():
        pair_key = tuple(sorted([edge.u, edge.v]))
        is_bidi = g.has_edge(edge.v, edge.u)

        if is_bidi:
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            arrows = {"to": {"enabled": False}}
            edge_id = f"{edge.u}<->{edge.v}"
        else:
            arrows = {"to": {"enabled": True, "scaleFactor": 0.7}}
            edge_id = f"{edge.u}->{edge.v}"

        tooltip = (
            f"<b>Link:</b> {sanitize_text(edge.u)} &harr; {sanitize_text(edge.v)}<br>"
            f"<b>Latency:</b> {edge.latency:.1f} ms<br>"
            f"<b>Bandwidth:</b> {edge.bandwidth_capacity:.0f} Mbps"
        )

        edges.append({
            "id": edge_id,
            "from": edge.u,
            "to": edge.v,
            "label": "",  # Empty by default for clean canvas readability
            "latency": edge.latency,
            "bandwidth": edge.bandwidth_capacity,
            "is_bidirectional": is_bidi,
            "arrows": arrows,
            "title": tooltip,
            "color": {"color": "#334155", "highlight": "#f97316", "hover": "#38bdf8"},
            "font": {"size": 11, "align": "middle", "color": "#f8fafc", "strokeWidth": 3, "strokeColor": "#090d16"},
            "smooth": {"type": "continuous"},
        })

    return {"nodes": nodes, "edges": edges}


@app.route("/")
def index():
    """Render main dashboard interface."""
    return render_template("index.html")


@app.route("/api/network", methods=["GET"])
def get_network():
    """Retrieve full active network topology in Vis.js format for the current session."""
    session_id = _get_session_id()
    entry = net_service.get_active_topology_entry(session_id)
    vis_data = format_graph_for_vis(entry["graph"])
    vis_data["topology_name"] = entry["name"]
    return jsonify(vis_data)


@app.route("/api/network/reset", methods=["POST"])
def reset_network():
    """Reset network to pristine baseline topology via service layer."""
    session_id = _get_session_id()
    result = net_service.reset_network(session_id=session_id)
    g = net_service.get_active_graph(session_id)
    result["network"] = format_graph_for_vis(g)
    return jsonify(result)


@app.route("/api/network/kill-edge", methods=["POST"])
def kill_random_edge():
    """Simulate link failure via service layer."""
    session_id = _get_session_id()
    data = request.get_json(silent=True) or {}
    edge_id = data.get("edge_id")

    try:
        result = net_service.kill_edge(edge_id=edge_id, session_id=session_id)
        g = net_service.get_active_graph(session_id)
        result["network"] = format_graph_for_vis(g)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/route", methods=["POST"])
def compute_route():
    """Compute shortest path or dual cross-validation comparison via service layer."""
    session_id = _get_session_id()
    data = request.get_json() or {}
    user_id = data.get("user_id")
    algorithm = data.get("algorithm", "bellman_ford").lower()

    if not user_id:
        return jsonify({"error": "Missing user_id parameter"}), 400

    try:
        if algorithm in ("compare", "compare_both"):
            result = net_service.compare_algorithms(source=user_id, session_id=session_id)
            result["mode"] = "comparison"
            result["user_id"] = user_id
            return jsonify(result)
        else:
            result = net_service.shortest_path(source=user_id, algo=algorithm, session_id=session_id)
            result["mode"] = "single"
            result["user_id"] = user_id
            return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/max-flow", methods=["POST"])
def compute_max_flow_api():
    """Execute max flow computation or dual comparison (Edmonds-Karp vs Ford-Fulkerson)."""
    session_id = _get_session_id()
    data = request.get_json() or {}
    source = data.get("source")
    sinks = data.get("sinks")
    algorithm = data.get("algorithm", "edmonds_karp").lower()

    try:
        if algorithm in ("compare", "compare_both"):
            ek_res = net_service.max_flow(source=source, sinks=sinks, algo="edmonds_karp", session_id=session_id)
            ff_res = net_service.max_flow(source=source, sinks=sinks, algo="ford_fulkerson", session_id=session_id)

            return jsonify({
                "mode": "comparison",
                "max_flow": ek_res["max_flow"],
                "edge_flows": ek_res["edge_flows"],
                "min_cut_edges": ek_res["min_cut_edges"],
                "min_cut_capacity": ek_res["min_cut_capacity"],
                "source": ek_res["source"],
                "sinks": ek_res["sinks"],
                "edmonds_karp": {
                    "algorithm": "Edmonds-Karp (BFS)",
                    "max_flow": ek_res["max_flow"],
                    "augmenting_paths": ek_res["augmenting_paths"],
                    "operations": ek_res["operations"],
                    "compute_time_ms": ek_res["compute_time_ms"],
                },
                "ford_fulkerson": {
                    "algorithm": "Ford-Fulkerson (DFS)",
                    "max_flow": ff_res["max_flow"],
                    "augmenting_paths": ff_res["augmenting_paths"],
                    "operations": ff_res["operations"],
                    "compute_time_ms": ff_res["compute_time_ms"],
                },
                "agreement": {
                    "matched": abs(ek_res["max_flow"] - ff_res["max_flow"]) < 1e-4,
                    "flow_diff": round(abs(ek_res["max_flow"] - ff_res["max_flow"]), 2),
                },
            })
        else:
            result = net_service.max_flow(source=source, sinks=sinks, algo=algorithm, session_id=session_id)
            result["mode"] = "single"
            return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/what-if", methods=["POST"])
def what_if_api():
    """Simulate counterfactual removals on a graph copy via service layer."""
    session_id = _get_session_id()
    data = request.get_json() or {}
    remove_nodes = data.get("remove_nodes")
    remove_edges = data.get("remove_edges")
    source = data.get("source")

    try:
        result = net_service.what_if(
            remove_nodes=remove_nodes,
            remove_edges=remove_edges,
            source=source,
            session_id=session_id,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/bottleneck", methods=["GET"])
def get_bottleneck_api():
    """Get network bottlenecks and min-cut via service layer."""
    session_id = _get_session_id()
    source = request.args.get("source")
    try:
        result = net_service.find_bottleneck(source=source, session_id=session_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/metrics", methods=["GET"])
def get_metrics_api():
    """Retrieve network metrics via service layer."""
    session_id = _get_session_id()
    metrics = net_service.get_metrics(session_id=session_id)
    return jsonify(metrics)


@app.route("/api/nodes", methods=["GET"])
def get_nodes_api():
    """Retrieve list of nodes in active topology."""
    session_id = _get_session_id()
    node_type = request.args.get("type")
    nodes = net_service.list_nodes(node_type=node_type, session_id=session_id)
    return jsonify({"nodes": nodes})


@app.route("/api/events", methods=["GET"])
def get_events_api():
    """Retrieve recent structured network events from SQLite Event Store."""
    session_id = _get_session_id()
    event_type = request.args.get("type")
    limit = int(request.args.get("limit", 50))
    events = get_event_store().list_events(session_id=session_id, event_type=event_type, limit=limit)
    return jsonify({"events": [e.to_dict() for e in events]})


@app.route("/api/benchmark-data", methods=["GET"])
def get_benchmark_data():
    """Read and return generated empirical benchmarking data."""
    csv_path = os.path.join(os.path.dirname(__file__), "..", "benchmarks", "results", "benchmark_results.csv")
    if not os.path.exists(csv_path):
        return jsonify({"error": "Benchmark data not generated yet."}), 404

    rows = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                "N": int(r["N"]),
                "Edges": int(r["Edges"]),
                "BF_Time_ms": float(r["BF_Time_ms"]),
                "BF_Operations": int(r["BF_Operations"]),
                "FW_Time_ms": float(r["FW_Time_ms"]),
                "FW_Operations": int(r["FW_Operations"]),
                "Theoretical_O_VE": int(r["Theoretical_O_VE"]),
                "Theoretical_O_V3": int(r["Theoretical_O_V3"]),
            })

    return jsonify({"benchmarks": rows})


@app.route("/api/benchmark-image", methods=["GET"])
def get_benchmark_image():
    """Serve the generated complexity benchmark plot."""
    img_path = os.path.join(os.path.dirname(__file__), "..", "benchmarks", "results", "complexity_benchmark.png")
    if not os.path.exists(img_path):
        return jsonify({"error": "Benchmark image not generated yet."}), 404
    return send_file(img_path, mimetype="image/png")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
