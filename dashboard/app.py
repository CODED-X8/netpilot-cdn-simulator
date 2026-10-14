"""Flask Web Dashboard backend for Mini CDN Routing Simulator."""

import os
import sys
import time
import random
import csv
from typing import Dict, Any, Optional

from flask import Flask, render_template, jsonify, request, send_file

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from graph.network import Graph
from graph.generator import generate_cdn_topology
from routing.bellman_ford import bellman_ford, find_best_edge_server_bf
from routing.floyd_warshall import floyd_warshall, find_best_edge_server_fw

app = Flask(__name__)

# In-memory active graph state
ACTIVE_GRAPH: Graph = generate_cdn_topology(num_origins=1, num_edges=8, num_users=5, seed=42)
INITIAL_SEED = 42


def format_graph_for_vis(g: Graph) -> Dict[str, Any]:
    """Transform Graph data structure into Vis.js network format with clean readability."""
    nodes = []
    for node in g.get_nodes():
        tier = node.metadata.get("tier", "edge")

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
        elif tier == "transit":
            # Regional ISP / Transit Relay
            shape = "dot"
            color = {
                "background": "#8b5cf6",
                "border": "#6d28d9",
                "highlight": {"background": "#c4b5fd", "border": "#5b21b6"},
            }
            size = 15
            font = {"color": "#cbd5e1", "face": "system-ui", "size": 10, "strokeWidth": 2, "strokeColor": "#0f172a"}
        else:  # primary user_region
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
            "label": node.label,
            "node_type": node.node_type,
            "tier": tier,
            "shape": shape,
            "color": color,
            "size": size,
            "font": font,
            "title": f"<b>{node.label}</b><br>ID: <code>{node.id}</code><br>Type: {node.node_type}",
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

        # Latency shown in hover tooltip; direct label is blank by default to eliminate clutter
        tooltip = (
            f"<b>Link:</b> {edge.u} &harr; {edge.v}<br>"
            f"<b>Latency:</b> {edge.latency:.1f} ms<br>"
            f"<b>Bandwidth:</b> {edge.bandwidth_capacity:.0f} Mbps"
        )

        edges.append({
            "id": edge_id,
            "from": edge.u,
            "to": edge.v,
            "label": "",  # Empty by default for canvas readability
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
    """Retrieve full active network topology in Vis.js format."""
    return jsonify(format_graph_for_vis(ACTIVE_GRAPH))


@app.route("/api/network/reset", methods=["POST"])
def reset_network():
    """Reset network to pristine baseline topology."""
    global ACTIVE_GRAPH
    ACTIVE_GRAPH = generate_cdn_topology(num_origins=1, num_edges=8, num_users=5, seed=INITIAL_SEED)
    return jsonify({
        "status": "success",
        "message": "Network reset to initial baseline topology.",
        "network": format_graph_for_vis(ACTIVE_GRAPH),
    })


@app.route("/api/route", methods=["POST"])
def compute_route():
    """Compute shortest path with support for single algorithm or dual cross-validation comparison."""
    data = request.get_json() or {}
    user_id = data.get("user_id")
    algorithm = data.get("algorithm", "bellman_ford").lower()

    if not user_id or not ACTIVE_GRAPH.has_node(user_id):
        return jsonify({"error": f"Invalid or missing user_region: '{user_id}'"}), 400

    node = ACTIVE_GRAPH.get_node(user_id)
    if node.node_type != "user_region":
        return jsonify({"error": f"Node '{user_id}' is of type '{node.node_type}', expected 'user_region'"}), 400

    # Cross-validation mode: Run BOTH Bellman-Ford & Floyd-Warshall
    if algorithm in ("compare", "compare_both"):
        # Bellman-Ford execution
        t0 = time.perf_counter()
        bf_res = find_best_edge_server_bf(ACTIVE_GRAPH, user_id, early_stopping=False)
        t1 = time.perf_counter()
        bf_time_ms = round((t1 - t0) * 1000.0, 4)

        # Floyd-Warshall execution
        t0 = time.perf_counter()
        fw_res = find_best_edge_server_fw(ACTIVE_GRAPH, user_id)
        t1 = time.perf_counter()
        fw_time_ms = round((t1 - t0) * 1000.0, 4)

        bf_lat = bf_res.get("latency")
        fw_lat = fw_res.get("latency")
        matched = (bf_lat is not None and fw_lat is not None and abs(bf_lat - fw_lat) < 1e-4)

        path = bf_res.get("path") or []
        path_edges = []
        for i in range(len(path) - 1):
            path_edges.append({"from": path[i], "to": path[i + 1]})

        return jsonify({
            "mode": "comparison",
            "user_id": user_id,
            "path": path,
            "path_edges": path_edges,
            "best_edge": bf_res.get("best_edge"),
            "latency": bf_lat,
            "bellman_ford": {
                "algorithm": "Bellman-Ford",
                "complexity": "O(|V| * |E|)",
                "best_edge": bf_res.get("best_edge"),
                "latency": bf_lat,
                "path": bf_res.get("path"),
                "operations": bf_res.get("operations"),
                "execution_time_ms": bf_time_ms,
            },
            "floyd_warshall": {
                "algorithm": "Floyd-Warshall",
                "complexity": "O(|V|^3)",
                "best_edge": fw_res.get("best_edge"),
                "latency": fw_lat,
                "path": fw_res.get("path"),
                "operations": fw_res.get("operations"),
                "execution_time_ms": fw_time_ms,
            },
            "agreement": {
                "matched": matched,
                "best_edge_match": bf_res.get("best_edge") == fw_res.get("best_edge"),
                "latency_diff": round(abs((bf_lat or 0) - (fw_lat or 0)), 4),
            },
            "node_count": len(ACTIVE_GRAPH),
            "edge_count": ACTIVE_GRAPH.edge_count(),
        })

    # Single algorithm execution
    t0 = time.perf_counter()
    if algorithm == "bellman_ford":
        result = find_best_edge_server_bf(ACTIVE_GRAPH, user_id, early_stopping=False)
        complexity = "O(|V| * |E|)"
    elif algorithm == "floyd_warshall":
        result = find_best_edge_server_fw(ACTIVE_GRAPH, user_id)
        complexity = "O(|V|^3)"
    else:
        return jsonify({"error": f"Unsupported algorithm '{algorithm}'"}), 400
    t1 = time.perf_counter()

    exec_time_ms = round((t1 - t0) * 1000.0, 4)
    path = result.get("path") or []
    path_edges = []
    for i in range(len(path) - 1):
        path_edges.append({"from": path[i], "to": path[i + 1]})

    return jsonify({
        "mode": "single",
        "user_id": user_id,
        "best_edge": result.get("best_edge"),
        "latency": result.get("latency"),
        "path": path,
        "path_edges": path_edges,
        "operations": result.get("operations"),
        "execution_time_ms": exec_time_ms,
        "algorithm": result.get("algorithm"),
        "complexity": complexity,
        "node_count": len(ACTIVE_GRAPH),
        "edge_count": ACTIVE_GRAPH.edge_count(),
    })


@app.route("/api/network/kill-edge", methods=["POST"])
def kill_random_edge():
    """Simulate link failure by removing an edge from the active network."""
    edges = ACTIVE_GRAPH.get_edges()
    if not edges:
        return jsonify({"error": "No edges remaining in the network."}), 400

    chosen_edge = random.choice(edges)
    u, v = chosen_edge.u, chosen_edge.v
    lat = chosen_edge.latency

    ACTIVE_GRAPH.remove_edge(u, v, bidirectional=True)

    return jsonify({
        "status": "success",
        "killed_edge": {"u": u, "v": v, "latency": lat},
        "remaining_edges": ACTIVE_GRAPH.edge_count(),
        "network": format_graph_for_vis(ACTIVE_GRAPH),
    })


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
