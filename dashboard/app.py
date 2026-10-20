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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from copilot.llm_provider import load_dotenv
load_dotenv()

from graph.network import Graph
import services.network_service as net_service
import services.topology_service as topo_service
from services.topology_service import TopologyValidationError
from storage.event_store import get_event_store
from copilot.agent import run_copilot_chat
from copilot.guardrails import (
    is_copilot_enabled,
    check_rate_limit,
    check_daily_token_budget,
    record_tokens_consumed,
)

DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(DASHBOARD_DIR, "templates"),
    static_folder=os.path.join(DASHBOARD_DIR, "static"),
    static_url_path="/static",
)


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


@app.route("/api/routing/trace", methods=["POST", "GET"])
def get_routing_trace_api():
    """Retrieve step-by-step trace for Bellman-Ford or Floyd-Warshall on topologies <= 30 nodes."""
    session_id = _get_session_id()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
    else:
        data = request.args

    user_id = data.get("user_id") or data.get("source")
    algorithm = data.get("algorithm", "bellman_ford").lower()

    if not user_id:
        return jsonify({"error": "Missing user_id / source parameter"}), 400

    try:
        result = net_service.explain_route_trace(source=user_id, algo=algorithm, session_id=session_id)
        return jsonify(result)
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to generate trace: {str(e)}"}), 500


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


@app.route("/api/topology/upload", methods=["POST"])
def upload_topology_api():
    """Upload a network topology from JSON or two CSVs (nodes.csv, edges.csv)."""
    session_id = _get_session_id()
    content_type = request.content_type or ""

    try:
        # 1. JSON payload
        if "application/json" in content_type:
            raw_text = request.get_data(as_text=True)
            graph, top_name, warnings = topo_service.parse_json_topology(raw_text)

        # 2. Multipart form upload
        elif "multipart/form-data" in content_type:
            # Check single JSON file
            if "file" in request.files and request.files["file"].filename:
                f = request.files["file"]
                raw_text = f.read().decode("utf-8", errors="replace")
                graph, top_name, warnings = topo_service.parse_json_topology(raw_text)
            # Check two CSV files: nodes_file and edges_file
            elif "nodes_file" in request.files and "edges_file" in request.files:
                nodes_text = request.files["nodes_file"].read().decode("utf-8", errors="replace")
                edges_text = request.files["edges_file"].read().decode("utf-8", errors="replace")
                top_name = request.form.get("name") or "Uploaded CSV Topology"
                graph, top_name, warnings = topo_service.parse_csv_topology(nodes_text, edges_text, name=top_name)
            else:
                return jsonify({
                    "error": "Upload missing file payload. Provide 'file' (JSON) or 'nodes_file' and 'edges_file' (CSV)."
                }), 400
        else:
            # Fallback raw data
            raw_text = request.get_data(as_text=True)
            graph, top_name, warnings = topo_service.parse_json_topology(raw_text)

        # Update active graph for this session
        net_service.set_active_graph(graph, name=top_name, session_id=session_id)

        # Log event
        get_event_store().log_event(
            event_type="topology_upload",
            session_id=session_id,
            topology_name=top_name,
            inputs={"node_count": len(graph), "edge_count": graph.edge_count()},
            results={"status": "success", "warnings": warnings},
        )

        return jsonify({
            "status": "success",
            "message": f"Topology '{top_name}' successfully loaded.",
            "topology_name": top_name,
            "node_count": len(graph),
            "edge_count": graph.edge_count(),
            "warnings": warnings,
            "network": format_graph_for_vis(graph),
        })

    except TopologyValidationError as tve:
        return jsonify({
            "error": "Topology validation failed",
            "errors": tve.errors,
            "warnings": tve.warnings,
        }), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/topology/template", methods=["GET"])
def get_topology_template_api():
    """Download starter topology template (JSON or CSV)."""
    fmt = request.args.get("format", "json")
    tmpl = topo_service.get_template_files(fmt)
    return tmpl["content"], 200, {
        "Content-Type": tmpl["mimetype"],
        "Content-Disposition": f"attachment; filename={tmpl['filename']}",
    }


@app.route("/api/topology/samples", methods=["GET"])
def get_sample_topologies_api():
    """List available sample topologies."""
    samples_dir = os.path.join(os.path.dirname(__file__), "..", "samples")
    sample_files = []
    if os.path.exists(samples_dir):
        for fname in os.listdir(samples_dir):
            if fname.endswith(".json"):
                fpath = os.path.join(samples_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        sample_files.append({
                            "id": fname,
                            "name": data.get("name", fname),
                            "description": data.get("description", ""),
                            "node_count": len(data.get("nodes", [])),
                            "edge_count": len(data.get("edges", [])),
                        })
                except Exception:
                    pass
    return jsonify({"samples": sample_files})


@app.route("/api/topology/load-sample", methods=["POST"])
def load_sample_topology_api():
    """Load a prebuilt sample topology into current session."""
    session_id = _get_session_id()
    data = request.get_json() or {}
    sample_id = data.get("sample_id", "campus_network.json")

    samples_dir = os.path.join(os.path.dirname(__file__), "..", "samples")
    target_path = os.path.join(samples_dir, os.path.basename(sample_id))

    if not os.path.exists(target_path):
        return jsonify({"error": f"Sample topology '{sample_id}' not found."}), 404

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
        graph, top_name, warnings = topo_service.parse_json_topology(raw_text)
        net_service.set_active_graph(graph, name=top_name, session_id=session_id)

        get_event_store().log_event(
            event_type="topology_upload",
            session_id=session_id,
            topology_name=top_name,
            inputs={"sample_id": sample_id},
            results={"status": "success"},
        )

        return jsonify({
            "status": "success",
            "message": f"Sample topology '{top_name}' loaded.",
            "topology_name": top_name,
            "warnings": warnings,
            "network": format_graph_for_vis(graph),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/copilot/chat", methods=["POST"])
def copilot_chat_api():
    """Chat endpoint for NetPilot AI Copilot with guardrails (kill switch, rate limit, token budget)."""
    # 1. Global kill switch check
    if not is_copilot_enabled():
        return jsonify({
            "error": "NetPilot Copilot has been administratively disabled via COPILOT_ENABLED."
        }), 503

    session_id = _get_session_id()

    # 2. Per-session rate limiter check
    allowed, retry_after = check_rate_limit(session_id)
    if not allowed:
        resp = jsonify({
            "error": f"Rate limit exceeded. Try again in {retry_after} seconds."
        })
        resp.status_code = 429
        resp.headers["Retry-After"] = str(retry_after)
        return resp

    # 3. Daily token budget check
    budget_ok, used, budget = check_daily_token_budget()
    if not budget_ok:
        return jsonify({
            "error": f"Daily token budget exhausted ({used}/{budget} tokens used). Resets at midnight UTC."
        }), 429

    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    history = data.get("history", [])
    confirm_action = data.get("confirm_action")

    if not message and not confirm_action:
        return jsonify({"error": "Missing message or confirm_action in request"}), 400

    try:
        response_data = run_copilot_chat(
            message=message,
            session_id=session_id,
            history=history,
            confirm_action=confirm_action,
        )
        # Record tokens consumed today
        record_tokens_consumed(response_data.get("tokens", 0))
        return jsonify(response_data)
    except Exception as e:
        return jsonify({"error": f"Copilot error: {str(e)}"}), 500


@app.route("/api/postmortem/generate", methods=["POST"])
def generate_postmortem_api():
    """Generate structured markdown postmortem report from event history."""
    session_id = _get_session_id()
    data = request.get_json(silent=True) or {}
    event_id = data.get("event_id")
    time_window = data.get("time_window_minutes", 60)

    try:
        from services.postmortem_service import generate_postmortem
        result = generate_postmortem(
            event_id=event_id,
            session_id=session_id,
            time_window_minutes=time_window,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Postmortem generation failed: {str(e)}"}), 500


@app.route("/api/mitigations/propose", methods=["POST"])
def propose_mitigations_api():
    """Propose, simulate on copies, and rank candidate mitigations."""
    session_id = _get_session_id()
    data = request.get_json(silent=True) or {}
    goal = data.get("goal", "maximize throughput")

    try:
        from services.mitigation_service import propose_and_simulate_mitigations
        result = propose_and_simulate_mitigations(goal=goal, session_id=session_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Mitigation proposal failed: {str(e)}"}), 500


@app.route("/api/mitigations/apply", methods=["POST"])
def apply_mitigation_api():
    """Apply a confirmed mitigation to the live graph."""
    session_id = _get_session_id()
    data = request.get_json(silent=True) or {}
    candidate = data.get("candidate", {})
    confirmed = data.get("confirmed", False)

    try:
        from services.mitigation_service import apply_mitigation
        result = apply_mitigation(candidate=candidate, session_id=session_id, confirmed=confirmed)
        if result.get("status") == "confirmation_required":
            return jsonify(result), 200

        # Include updated vis network
        graph = net_service.get_active_graph(session_id)
        result["network"] = format_graph_for_vis(graph)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Applying mitigation failed: {str(e)}"}), 500


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
                "Dijk_Time_ms": float(r.get("Dijk_Time_ms", 0.0)),
                "Dijk_Operations": int(r.get("Dijk_Operations", 0)),
                "Theoretical_O_VE": int(r["Theoretical_O_VE"]),
                "Theoretical_O_V3": int(r["Theoretical_O_V3"]),
                "Theoretical_O_E_log_V": int(r.get("Theoretical_O_E_log_V", 0)),
            })

    return jsonify({"benchmarks": rows})


@app.route("/api/benchmark-image", methods=["GET"])
def get_benchmark_image():
    """Serve the generated complexity benchmark plot."""
    img_path = os.path.join(os.path.dirname(__file__), "..", "benchmarks", "results", "complexity_benchmark.png")
    if not os.path.exists(img_path):
        return jsonify({"error": "Benchmark image not generated yet."}), 404
    return send_file(img_path, mimetype="image/png")


@app.route("/api/llmops/stats", methods=["GET"])
def get_llmops_stats_api():
    """Return LLMOps metrics, benchmark comparison, token budget, runbook coverage, and sanitized audit log."""
    from copilot.guardrails import get_daily_token_usage
    from rag.vector_store import get_vector_store

    # 1. Benchmark Evaluation Findings
    eval_summary_path = os.path.join(os.path.dirname(__file__), "..", "eval", "results", "eval_summary.json")
    eval_summary: Dict[str, Any] = {}
    is_real_run = False
    run_message = "No evaluation run executed yet."

    if os.path.exists(eval_summary_path):
        try:
            with open(eval_summary_path, "r", encoding="utf-8") as f:
                eval_summary = json.load(f)
            meta = eval_summary.get("meta", {})
            is_dry = meta.get("is_dry_run", True)
            prov = meta.get("provider", "fake")
            if not is_dry and prov not in ("fake", "mock"):
                is_real_run = True
                run_message = f"Live Evaluation Run ({prov} / {meta.get('model')})"
            else:
                is_real_run = False
                run_message = "No real evaluation run yet (Dry-run / Synthetic baseline data only)"
        except Exception:
            eval_summary = {}

    # 2. Token Budget Gauge
    used_tokens, max_budget = get_daily_token_usage()
    percent_budget = round((used_tokens / max_budget) * 100, 1) if max_budget > 0 else 0.0

    # 3. Runbook Knowledge Base Health & Coverage
    vs = get_vector_store()
    chunk_count = vs.get_document_count()
    runbooks_dir = os.path.join(os.path.dirname(__file__), "..", "runbooks")
    runbook_files = []
    if os.path.exists(runbooks_dir):
        for fname in sorted(os.listdir(runbooks_dir)):
            if fname.endswith(".md"):
                fpath = os.path.join(runbooks_dir, fname)
                runbook_files.append({
                    "name": html.escape(fname),
                    "size_bytes": os.path.getsize(fpath),
                })

    # 4. Recent Audit Log (Last 10 events, fully escaped & redacted)
    es = get_event_store()
    events = es.list_events(limit=10)
    audit_log = []
    sensitive_keys = {"api_key", "key", "secret", "password", "prompt", "system_prompt", "token"}

    for ev in events:
        # Sanitize and redact inputs
        clean_inputs = {}
        if isinstance(ev.inputs, dict):
            for k, v in ev.inputs.items():
                if any(sk in k.lower() for sk in sensitive_keys):
                    clean_inputs[html.escape(str(k))] = "[REDACTED]"
                else:
                    clean_inputs[html.escape(str(k))] = html.escape(str(v)[:100])

        # Sanitize and redact results
        clean_results = {}
        if isinstance(ev.results, dict):
            for k, v in ev.results.items():
                if any(sk in k.lower() for sk in sensitive_keys):
                    clean_results[html.escape(str(k))] = "[REDACTED]"
                else:
                    clean_results[html.escape(str(k))] = html.escape(str(v)[:100])

        audit_log.append({
            "id": ev.id,
            "event_type": html.escape(ev.type),
            "topology_name": html.escape(ev.topology_name),
            "timestamp": ev.timestamp,
            "duration_ms": round(ev.compute_time_ms, 2),
            "inputs": clean_inputs,
            "results": clean_results,
            "verifier_status": "verified" if ev.type in ("shortest_path", "compare_algorithms", "max_flow", "apply_mitigation") else "audit_logged",
        })

    has_plot = os.path.exists(os.path.join(os.path.dirname(__file__), "..", "eval", "results", "eval_comparison.png"))

    return jsonify({
        "status": "success",
        "is_real_run": is_real_run,
        "run_message": run_message,
        "evaluation_summary": eval_summary,
        "has_comparison_plot": has_plot,
        "token_budget": {
            "used": used_tokens,
            "limit": max_budget,
            "percent": percent_budget,
            "remaining": max(0, max_budget - used_tokens),
        },
        "runbook_coverage": {
            "total_chunks": chunk_count,
            "runbook_count": len(runbook_files),
            "runbooks": runbook_files,
            "status": "healthy",
        },
        "audit_log": audit_log,
    })


@app.route("/api/llmops/plot", methods=["GET"])
def get_llmops_plot_api():
    """Serve the generated evaluation comparison chart."""
    img_path = os.path.join(os.path.dirname(__file__), "..", "eval", "results", "eval_comparison.png")
    if not os.path.exists(img_path):
        return jsonify({"error": "Evaluation comparison image not generated yet."}), 404
    return send_file(img_path, mimetype="image/png")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
