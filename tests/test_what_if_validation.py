"""Tests for edge validation, bidirectional parsing, and what-if shortest path mutation."""

import pytest
from graph.generator import generate_cdn_topology
from services.network_service import what_if, kill_edge, shortest_path


def test_what_if_unknown_edge_raises_error():
    g = generate_cdn_topology(seed=42)
    with pytest.raises(ValueError, match="Unknown edge|not found"):
        what_if(remove_edges=["nonexistent_u<->nonexistent_v"], graph=g)


def test_what_if_malformed_edge_raises_error():
    g = generate_cdn_topology(seed=42)
    with pytest.raises(ValueError, match="Malformed edge identifier"):
        what_if(remove_edges=["bad_edge_no_separator"], graph=g)


def test_kill_edge_unknown_edge_raises_error():
    g = generate_cdn_topology(seed=42)
    with pytest.raises(ValueError, match="Unknown edge|not found"):
        kill_edge(edge_id="fake_a<->fake_b", graph=g)


def test_what_if_accepts_bidirectional_representations():
    g = generate_cdn_topology(seed=42)
    edge = g.get_edges()[0]
    u, v = edge.u, edge.v

    # Test forward representation u<->v
    res_fwd = what_if(remove_edges=[f"{u}<->{v}"], graph=g)
    assert f"{u}<->{v}" in res_fwd["removed_edges"] or f"{v}<->{u}" in res_fwd["removed_edges"]

    # Test reverse representation v<->u
    res_rev = what_if(remove_edges=[f"{v}<->{u}"], graph=g)
    assert f"{u}<->{v}" in res_rev["removed_edges"] or f"{v}<->{u}" in res_rev["removed_edges"]


def test_removing_edge_on_shortest_path_changes_path_or_no_route():
    g = generate_cdn_topology(seed=42)
    source = "user_1"

    # Compute baseline route
    base_route = shortest_path(source=source, graph=g)
    path = base_route["path"]
    assert len(path) >= 2, "Path must have at least one edge"

    # Pick the critical first edge on the shortest path
    crit_u, crit_v = path[0], path[1]
    edge_str = f"{crit_u}<->{crit_v}"

    # Simulate removing this critical edge
    sim_res = what_if(remove_edges=[edge_str], source=source, graph=g)

    # Assert that the path changed or there is no route
    sim_path = sim_res["after"]["path"]
    assert sim_path != path or sim_res["after"]["latency"] is None, (
        f"Simulated path {sim_path} must differ from baseline path {path} when critical edge {edge_str} is removed"
    )
    if sim_res["after"]["latency"] is not None:
        assert sim_res["after"]["latency"] >= base_route["latency"]
