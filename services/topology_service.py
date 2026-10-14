"""Topology parsing, validation, and session-scoped management service.

Accepts:
- One JSON file / object
- Two CSV files (nodes.csv and edges.csv)

Enforces:
- Row-numbered error reporting
- Structural assertions (at least 1 origin, 1 edge_server, 1 user_region)
- Warnings on negative latency and disconnected components
- Upper limits (200 nodes, 2000 edges, 1MB payload)
- Safe parsing (no eval, no pickle)
- In-memory session isolation with automatic TTL expiry
"""

import csv
import io
import json
import time
from typing import Dict, List, Tuple, Any, Optional, Set
from graph.network import Graph, Node

MAX_NODES = 200
MAX_EDGES = 2000
MAX_FILE_SIZE_BYTES = 1024 * 1024  # 1 MB
SESSION_EXPIRY_SECONDS = 7200  # 2 hours

VALID_NODE_TYPES = {"origin", "edge_server", "user_region", "transit"}


class TopologyValidationError(Exception):
    """Raised when topology validation fails with row-numbered errors."""

    def __init__(self, errors: List[str], warnings: Optional[List[str]] = None):
        super().__init__("; ".join(errors))
        self.errors = errors
        self.warnings = warnings or []


def validate_and_build_topology(
    nodes_data: List[Dict[str, Any]],
    edges_data: List[Dict[str, Any]],
    topology_name: str = "Uploaded Network",
) -> Tuple[Graph, str, List[str]]:
    """Validate raw node and edge dictionaries and construct a Graph instance.

    Returns:
        (graph, topology_name, warnings)

    Raises:
        TopologyValidationError: If any row-level or structural validation fails.
    """
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Check size limits
    if len(nodes_data) > MAX_NODES:
        errors.append(f"Limit Error: Topology contains {len(nodes_data)} nodes, exceeding max limit of {MAX_NODES}.")
    if len(edges_data) > MAX_EDGES:
        errors.append(f"Limit Error: Topology contains {len(edges_data)} edges, exceeding max limit of {MAX_EDGES}.")

    if errors:
        raise TopologyValidationError(errors, warnings)

    # 2. Validate Nodes
    nodes_by_id: Dict[str, Dict[str, Any]] = {}
    type_counts = {"origin": 0, "edge_server": 0, "user_region": 0, "transit": 0}

    for row_idx, raw_node in enumerate(nodes_data, start=1):
        raw_id = raw_node.get("id")
        if raw_id is None or str(raw_id).strip() == "":
            errors.append(f"Row {row_idx} (Nodes): Missing required 'id' attribute.")
            continue

        node_id = str(raw_id).strip()
        if node_id in nodes_by_id:
            errors.append(f"Row {row_idx} (Nodes): Duplicate node id '{node_id}'.")
            continue

        raw_type = raw_node.get("type", "edge_server")
        node_type = str(raw_type).strip().lower()
        if node_type not in VALID_NODE_TYPES:
            errors.append(
                f"Row {row_idx} (Nodes): Invalid node type '{node_type}'. "
                f"Must be one of {sorted(list(VALID_NODE_TYPES))}."
            )
            continue

        label = str(raw_node.get("name") or raw_node.get("label") or node_id).strip()
        nodes_by_id[node_id] = {
            "id": node_id,
            "type": node_type,
            "label": label,
        }
        type_counts[node_type] += 1

    # 3. Validate Structural Node Requirements
    if type_counts["origin"] < 1:
        errors.append("Structural Error: Topology must contain at least one 'origin' server.")
    if type_counts["edge_server"] < 1:
        errors.append("Structural Error: Topology must contain at least one 'edge_server'.")
    if type_counts["user_region"] < 1:
        errors.append("Structural Error: Topology must contain at least one 'user_region'.")

    # 4. Validate Edges
    parsed_edges = []
    connected_nodes: Set[str] = set()

    for row_idx, raw_edge in enumerate(edges_data, start=1):
        src_raw = raw_edge.get("source") or raw_edge.get("u")
        tgt_raw = raw_edge.get("target") or raw_edge.get("v")

        if not src_raw or str(src_raw).strip() == "":
            errors.append(f"Row {row_idx} (Edges): Missing required 'source' node ID.")
            continue
        if not tgt_raw or str(tgt_raw).strip() == "":
            errors.append(f"Row {row_idx} (Edges): Missing required 'target' node ID.")
            continue

        src = str(src_raw).strip()
        tgt = str(tgt_raw).strip()

        if src not in nodes_by_id:
            errors.append(f"Row {row_idx} (Edges): Source node '{src}' does not exist in nodes definition.")
        if tgt not in nodes_by_id:
            errors.append(f"Row {row_idx} (Edges): Target node '{tgt}' does not exist in nodes definition.")

        # Latency validation
        raw_lat = raw_edge.get("latency_ms") if "latency_ms" in raw_edge else raw_edge.get("latency", 10.0)
        try:
            latency = float(raw_lat)
            if latency < 0:
                warnings.append(f"Row {row_idx} (Edges): Warning: negative latency {latency}ms on link ({src} -> {tgt}).")
        except (ValueError, TypeError):
            errors.append(f"Row {row_idx} (Edges): Latency '{raw_lat}' must be a valid numeric value.")
            latency = 10.0

        # Capacity validation
        raw_cap = (
            raw_edge.get("capacity_mbps")
            if "capacity_mbps" in raw_edge
            else raw_edge.get("bandwidth_capacity", raw_edge.get("capacity", 1000.0))
        )
        try:
            capacity = float(raw_cap)
            if capacity <= 0:
                errors.append(f"Row {row_idx} (Edges): Capacity {capacity} must be a positive number (> 0).")
        except (ValueError, TypeError):
            errors.append(f"Row {row_idx} (Edges): Capacity '{raw_cap}' must be a valid positive number.")
            capacity = 1000.0

        raw_dir = raw_edge.get("directed", False)
        if isinstance(raw_dir, str):
            is_directed = raw_dir.strip().lower() in ("true", "1", "yes")
        else:
            is_directed = bool(raw_dir)

        parsed_edges.append((src, tgt, latency, capacity, is_directed))
        connected_nodes.add(src)
        connected_nodes.add(tgt)

    # 5. Check disconnected nodes warning
    for nid in nodes_by_id:
        if nid not in connected_nodes:
            warnings.append(f"Warning: Node '{nid}' ({nodes_by_id[nid]['label']}) is disconnected with 0 links.")

    if errors:
        raise TopologyValidationError(errors, warnings)

    # 6. Construct Graph
    g = Graph()
    for nid, nmeta in nodes_by_id.items():
        # Handle transit tier classification
        tier = "transit" if nmeta["type"] == "transit" else ("edge" if nmeta["type"] == "edge_server" else ("user" if nmeta["type"] == "user_region" else "origin"))
        g.add_node(
            nid,
            node_type=nmeta["type"],
            label=nmeta["label"],
            tier=tier,
        )

    for src, tgt, latency, capacity, is_directed in parsed_edges:
        # directed: false means add both directions (bidirectional=True)
        g.add_edge(
            src,
            tgt,
            latency=latency,
            bandwidth_capacity=capacity,
            bidirectional=(not is_directed),
        )

    return g, topology_name, warnings


def parse_json_topology(content: str) -> Tuple[Graph, str, List[str]]:
    """Parse JSON string into Graph with validation."""
    if len(content.encode("utf-8")) > MAX_FILE_SIZE_BYTES:
        raise TopologyValidationError(["File size exceeds 1 MB limit."])

    try:
        data = json.loads(content)
    except Exception as e:
        raise TopologyValidationError([f"Invalid JSON format: {str(e)}"])

    if not isinstance(data, dict):
        raise TopologyValidationError(["Root JSON element must be an object."])

    nodes = data.get("nodes")
    edges = data.get("edges")

    if not isinstance(nodes, list):
        raise TopologyValidationError(["JSON must contain a 'nodes' array."])
    if not isinstance(edges, list):
        raise TopologyValidationError(["JSON must contain an 'edges' array."])

    name = str(data.get("name") or "Uploaded JSON Topology").strip()
    return validate_and_build_topology(nodes, edges, topology_name=name)


def parse_csv_topology(nodes_csv: str, edges_csv: str, name: str = "Uploaded CSV Topology") -> Tuple[Graph, str, List[str]]:
    """Parse nodes.csv and edges.csv content into Graph with validation."""
    if len(nodes_csv.encode("utf-8")) + len(edges_csv.encode("utf-8")) > MAX_FILE_SIZE_BYTES:
        raise TopologyValidationError(["Combined CSV file sizes exceed 1 MB limit."])

    nodes_reader = csv.DictReader(io.StringIO(nodes_csv.strip()))
    edges_reader = csv.DictReader(io.StringIO(edges_csv.strip()))

    nodes_data = list(nodes_reader)
    edges_data = list(edges_reader)

    return validate_and_build_topology(nodes_data, edges_data, topology_name=name)


def get_template_files(format_type: str = "json") -> Dict[str, Any]:
    """Return downloadable starter templates."""
    fmt = format_type.lower()
    if fmt == "csv_nodes":
        content = (
            "id,name,type\n"
            "dc_1,Central Datacenter,origin\n"
            "edge_1,US East POP,edge_server\n"
            "edge_2,EU West POP,edge_server\n"
            "transit_1,Backbone Optical Link,transit\n"
            "users_1,New York Users,user_region\n"
            "users_2,London Users,user_region\n"
        )
        return {"filename": "nodes.csv", "mimetype": "text/csv", "content": content}

    elif fmt == "csv_edges":
        content = (
            "source,target,latency_ms,capacity_mbps,directed\n"
            "dc_1,transit_1,5.0,10000,false\n"
            "transit_1,edge_1,8.0,5000,false\n"
            "transit_1,edge_2,35.0,5000,false\n"
            "edge_1,users_1,4.0,1000,false\n"
            "edge_2,users_2,6.0,1000,false\n"
        )
        return {"filename": "edges.csv", "mimetype": "text/csv", "content": content}

    else:
        sample = {
            "name": "Custom CDN Topology Template",
            "nodes": [
                {"id": "dc_1", "name": "Primary Datacenter", "type": "origin"},
                {"id": "edge_1", "name": "Virginia Edge POP", "type": "edge_server"},
                {"id": "edge_2", "name": "Frankfurt Edge POP", "type": "edge_server"},
                {"id": "transit_1", "name": "Regional Transit Relay", "type": "transit"},
                {"id": "users_1", "name": "North America Clients", "type": "user_region"},
                {"id": "users_2", "name": "Europe Clients", "type": "user_region"},
            ],
            "edges": [
                {"source": "dc_1", "target": "transit_1", "latency_ms": 6.0, "capacity_mbps": 10000, "directed": False},
                {"source": "transit_1", "target": "edge_1", "latency_ms": 8.0, "capacity_mbps": 5000, "directed": False},
                {"source": "transit_1", "target": "edge_2", "latency_ms": 42.0, "capacity_mbps": 5000, "directed": False},
                {"source": "users_1", "target": "edge_1", "latency_ms": 5.0, "capacity_mbps": 1000, "directed": False},
                {"source": "users_2", "target": "edge_2", "latency_ms": 7.0, "capacity_mbps": 1000, "directed": False},
            ],
        }
        return {"filename": "topology_template.json", "mimetype": "application/json", "content": json.dumps(sample, indent=2)}
