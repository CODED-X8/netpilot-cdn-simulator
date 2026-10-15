"""Tests for topology parsing, validation, row-numbered error reporting, and templates."""

import pytest
from services.topology_service import (
    parse_json_topology,
    parse_csv_topology,
    validate_and_build_topology,
    TopologyValidationError,
    get_template_files,
)


def test_valid_json_topology():
    """Verify parsing a valid JSON topology builds a Graph correctly."""
    valid_json = """
    {
      "name": "Test Valid Topology",
      "nodes": [
        {"id": "o1", "name": "Origin Datacenter", "type": "origin"},
        {"id": "e1", "name": "Edge Server Alpha", "type": "edge_server"},
        {"id": "u1", "name": "Users Beta", "type": "user_region"}
      ],
      "edges": [
        {"source": "o1", "target": "e1", "latency_ms": 15.0, "capacity_mbps": 5000.0, "directed": false},
        {"source": "u1", "target": "e1", "latency_ms": 10.0, "capacity_mbps": 1000.0, "directed": false}
      ]
    }
    """
    graph, name, warnings = parse_json_topology(valid_json)
    assert name == "Test Valid Topology"
    assert len(graph) == 3
    assert graph.edge_count() == 4  # 2 undirected links = 4 directed edges
    assert len(warnings) == 0


def test_valid_csv_topology():
    """Verify parsing valid nodes.csv and edges.csv builds a Graph correctly."""
    nodes_csv = """id,name,type
origin_dc,Primary DC,origin
edge_lon,London POP,edge_server
users_uk,UK Users,user_region
transit_hub,Backbone Hub,transit
"""
    edges_csv = """source,target,latency_ms,capacity_mbps,directed
origin_dc,transit_hub,8.0,10000,false
transit_hub,edge_lon,12.0,5000,false
users_uk,edge_lon,5.0,1000,false
"""
    graph, name, warnings = parse_csv_topology(nodes_csv, edges_csv, name="Campus CSV Test")
    assert name == "Campus CSV Test"
    assert len(graph) == 4
    assert graph.edge_count() == 6
    assert len(warnings) == 0


def test_row_numbered_duplicate_node_error():
    """Assert duplicate node ID produces row-numbered error."""
    nodes = [
        {"id": "node_1", "type": "origin"},
        {"id": "node_1", "type": "edge_server"},
        {"id": "user_1", "type": "user_region"},
    ]
    edges = [
        {"source": "node_1", "target": "user_1", "latency_ms": 10.0, "capacity_mbps": 1000.0}
    ]

    with pytest.raises(TopologyValidationError) as exc_info:
        validate_and_build_topology(nodes, edges)

    errs = exc_info.value.errors
    assert any("Row 2 (Nodes): Duplicate node id 'node_1'" in e for e in errs)


def test_row_numbered_invalid_node_type_error():
    """Assert invalid node type produces row-numbered error."""
    nodes = [
        {"id": "o1", "type": "origin"},
        {"id": "e1", "type": "invalid_server_type"},
        {"id": "u1", "type": "user_region"},
    ]
    edges = [
        {"source": "o1", "target": "e1", "latency_ms": 10.0, "capacity_mbps": 1000.0}
    ]

    with pytest.raises(TopologyValidationError) as exc_info:
        validate_and_build_topology(nodes, edges)

    errs = exc_info.value.errors
    assert any("Row 2 (Nodes): Invalid node type 'invalid_server_type'" in e for e in errs)


def test_row_numbered_missing_edge_node_error():
    """Assert referencing non-existent node in edge produces row-numbered error."""
    nodes = [
        {"id": "o1", "type": "origin"},
        {"id": "e1", "type": "edge_server"},
        {"id": "u1", "type": "user_region"},
    ]
    edges = [
        {"source": "o1", "target": "non_existent_node", "latency_ms": 10.0, "capacity_mbps": 1000.0}
    ]

    with pytest.raises(TopologyValidationError) as exc_info:
        validate_and_build_topology(nodes, edges)

    errs = exc_info.value.errors
    assert any("Row 1 (Edges): Target node 'non_existent_node' does not exist" in e for e in errs)


def test_row_numbered_negative_capacity_error():
    """Assert negative capacity produces row-numbered error."""
    nodes = [
        {"id": "o1", "type": "origin"},
        {"id": "e1", "type": "edge_server"},
        {"id": "u1", "type": "user_region"},
    ]
    edges = [
        {"source": "o1", "target": "e1", "latency_ms": 10.0, "capacity_mbps": -500.0}
    ]

    with pytest.raises(TopologyValidationError) as exc_info:
        validate_and_build_topology(nodes, edges)

    errs = exc_info.value.errors
    assert any("Row 1 (Edges): Capacity -500.0 must be a positive number (> 0)" in e for e in errs)


def test_structural_missing_origin_error():
    """Assert topology lacking an origin server produces structural error."""
    nodes = [
        {"id": "e1", "type": "edge_server"},
        {"id": "u1", "type": "user_region"},
    ]
    edges = [
        {"source": "e1", "target": "u1", "latency_ms": 5.0, "capacity_mbps": 1000.0}
    ]

    with pytest.raises(TopologyValidationError) as exc_info:
        validate_and_build_topology(nodes, edges)

    errs = exc_info.value.errors
    assert any("Structural Error: Topology must contain at least one 'origin' server" in e for e in errs)


def test_warning_on_negative_latency_and_disconnected_node():
    """Assert negative latency and disconnected nodes produce warnings without failing validation."""
    nodes = [
        {"id": "o1", "type": "origin"},
        {"id": "e1", "type": "edge_server"},
        {"id": "u1", "type": "user_region"},
        {"id": "isolated_node", "type": "transit"},
    ]
    edges = [
        {"source": "o1", "target": "e1", "latency_ms": -4.5, "capacity_mbps": 1000.0},
        {"source": "e1", "target": "u1", "latency_ms": 10.0, "capacity_mbps": 1000.0},
    ]

    graph, _, warnings = validate_and_build_topology(nodes, edges)
    assert len(graph) == 4
    assert any("negative latency -4.5ms" in w for w in warnings)
    assert any("isolated_node" in w and "disconnected" in w for w in warnings)


def test_template_generation():
    """Assert template endpoints generate valid formats."""
    json_tmpl = get_template_files("json")
    assert json_tmpl["filename"] == "topology_template.json"
    assert "Primary Datacenter" in json_tmpl["content"]

    csv_nodes = get_template_files("csv_nodes")
    assert csv_nodes["filename"] == "nodes.csv"
    assert "id,name,type" in csv_nodes["content"]

    csv_edges = get_template_files("csv_edges")
    assert csv_edges["filename"] == "edges.csv"
    assert "source,target,latency_ms" in csv_edges["content"]


def test_college_campus_topology_sample():
    """Verify College Campus topology with Admin Building, AB1-AB4, and Hostel Blocks A-F."""
    import os
    from graph.generator import generate_college_campus_topology
    from routing.bellman_ford import find_best_edge_server_bf

    # 1. Test generator
    g = generate_college_campus_topology()
    assert g.has_node("Admin")
    assert g.has_node("AB1")
    assert g.has_node("AB2")
    assert g.has_node("AB3")
    assert g.has_node("AB4")
    for block in ["Hostel_A", "Hostel_B", "Hostel_C", "Hostel_D", "Hostel_E", "Hostel_F"]:
        assert g.has_node(block)
        route = find_best_edge_server_bf(g, block)
        assert route["best_edge"] in ["AB1", "AB2", "AB3", "AB4"]
        assert route["latency"] > 0

    # 2. Test JSON sample file
    sample_path = os.path.join(os.path.dirname(__file__), "..", "samples", "campus_network.json")
    with open(sample_path, "r", encoding="utf-8") as f:
        json_content = f.read()
    g_json, name, warnings = parse_json_topology(json_content)
    assert name == "College Campus Network"
    assert len(warnings) == 0
    assert g_json.has_node("Admin")
    assert g_json.has_node("AB1")

