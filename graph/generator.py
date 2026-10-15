"""CDN network topology generator for realistic network topologies and random benchmark graphs."""

import random
from typing import Optional
from .network import Graph


def generate_cdn_topology(
    num_origins: int = 1,
    num_edges: int = 8,
    num_users: int = 5,
    min_latency: float = 5.0,
    max_latency: float = 150.0,
    seed: Optional[int] = 42,
) -> Graph:
    """Generate a realistic hierarchical CDN topology with multi-hop access paths.

    Structure:
    1. Origin server: Central data repository.
    2. Edge servers (POPs): Core caching proxies interconnected via backbone mesh.
    3. User regions: Client populations. Some (Users 1-2) have direct access (1-2 hops),
       while remote populations (Users 3-5) route through regional ISP transit relays,
       guaranteeing multi-hop paths (3+ hops) for realistic pathfinding demos.

    Returns:
        Graph: Fully populated CDN graph.
    """
    if seed is not None:
        random.seed(seed)

    g = Graph()

    # 1. Add Origin Server(s)
    origin_ids = []
    for i in range(1, num_origins + 1):
        oid = f"origin_{i}"
        origin_ids.append(oid)
        g.add_node(
            oid,
            node_type="origin",
            label="Origin · Central DC",
            tier="origin",
            region="Global Central",
        )

    # 2. Add Edge Servers (Core POPs)
    edge_ids = []
    edge_names = [
        "Virginia",
        "Oregon",
        "Frankfurt",
        "Stockholm",
        "Tokyo",
        "Singapore",
        "São Paulo",
        "Cape Town",
    ]
    for i in range(1, num_edges + 1):
        eid = f"edge_{i}"
        edge_ids.append(eid)
        city = edge_names[(i - 1) % len(edge_names)]
        g.add_node(
            eid,
            node_type="edge_server",
            label=f"Edge {i} · {city}",
            tier="edge",
            city=city,
            cache_capacity_gb=random.randint(500, 2000),
        )

    # 3. Add Primary User Regions
    user_labels = [
        "User 1 · N. America",
        "User 2 · W. Europe",
        "User 3 · E. Asia",
        "User 4 · S. America",
        "User 5 · S. Asia",
    ]
    for i in range(1, num_users + 1):
        uid = f"user_{i}"
        label = user_labels[(i - 1) % len(user_labels)]
        g.add_node(
            uid,
            node_type="user_region",
            label=label,
            tier="user",
            client_density=random.randint(50000, 500000),
        )

    # 4. Add Regional Transit / ISP Aggregation Relays (classified as user_region tier="transit")
    # These create genuine 3+ hop paths for remote user populations (User 3, 4, 5)
    transit_nodes = [
        ("transit_apac_1", "ISP · Tokyo Ingress", "East Asia"),
        ("transit_apac_2", "Hub · Seoul Transit", "East Asia"),
        ("transit_latam_1", "ISP · Lima Relay", "South America"),
        ("transit_latam_2", "Hub · Bogota Transit", "South America"),
        ("transit_sasia_1", "ISP · Mumbai Ingress", "South Asia"),
        ("transit_sasia_2", "Hub · Colombo Transit", "South Asia"),
    ]
    for tid, tlabel, tregion in transit_nodes:
        g.add_node(
            tid,
            node_type="user_region",
            label=tlabel,
            tier="transit",
            region=tregion,
        )

    # --- Edge Connections ---

    # A. Origin to Edge Servers (Backbone Links)
    for eid in edge_ids:
        for oid in origin_ids:
            lat = round(random.uniform(35.0, 75.0), 1)
            bw = round(random.uniform(5000.0, 10000.0), 1)
            g.add_edge(oid, eid, latency=lat, bandwidth_capacity=bw, bidirectional=True)

    # B. Edge Server Interconnects (Peering Mesh Backbone)
    for i in range(len(edge_ids)):
        # Primary Ring
        next_i = (i + 1) % len(edge_ids)
        lat = round(random.uniform(12.0, 35.0), 1)
        bw = round(random.uniform(4000.0, 8000.0), 1)
        g.add_edge(edge_ids[i], edge_ids[next_i], latency=lat, bandwidth_capacity=bw, bidirectional=True)

        # Cross Chord for Redundancy
        chord_i = (i + 3) % len(edge_ids)
        if chord_i != i and chord_i != next_i and not g.has_edge(edge_ids[i], edge_ids[chord_i]):
            lat = round(random.uniform(25.0, 55.0), 1)
            bw = round(random.uniform(3000.0, 6000.0), 1)
            g.add_edge(edge_ids[i], edge_ids[chord_i], latency=lat, bandwidth_capacity=bw, bidirectional=True)

    # C. Access Links for Direct Users (Users 1 & 2 -> 1-2 hops)
    # User 1 (N. America) connects to Edge 1 (Virginia) and Edge 2 (Oregon)
    g.add_edge("user_1", "edge_1", latency=14.0, bandwidth_capacity=800.0, bidirectional=True)
    g.add_edge("user_1", "edge_2", latency=38.0, bandwidth_capacity=500.0, bidirectional=True)

    # User 2 (W. Europe) connects to Edge 3 (Frankfurt) and Edge 4 (Stockholm)
    g.add_edge("user_2", "edge_3", latency=16.0, bandwidth_capacity=800.0, bidirectional=True)
    g.add_edge("user_2", "edge_4", latency=32.0, bandwidth_capacity=500.0, bidirectional=True)

    # D. Multi-Hop Access Networks for Remote Users (Users 3, 4, 5 -> 3+ hops)

    # User 3 (E. Asia): user_3 -> transit_apac_1 (12ms) -> transit_apac_2 (14ms) -> edge_5 (Tokyo, 15ms) = 3 HOPS (41ms)
    # Alternative failover: transit_apac_1 -> edge_6 (Singapore, 55ms)
    g.add_edge("user_3", "transit_apac_1", latency=12.0, bandwidth_capacity=400.0, bidirectional=True)
    g.add_edge("transit_apac_1", "transit_apac_2", latency=14.0, bandwidth_capacity=600.0, bidirectional=True)
    g.add_edge("transit_apac_2", "edge_5", latency=15.0, bandwidth_capacity=1000.0, bidirectional=True)
    g.add_edge("transit_apac_1", "edge_6", latency=55.0, bandwidth_capacity=400.0, bidirectional=True)

    # User 4 (S. America): user_4 -> transit_latam_1 (15ms) -> transit_latam_2 (18ms) -> edge_7 (São Paulo, 20ms) = 3 HOPS (53ms)
    # Alternative failover: transit_latam_2 -> edge_1 (Virginia, 85ms)
    g.add_edge("user_4", "transit_latam_1", latency=15.0, bandwidth_capacity=300.0, bidirectional=True)
    g.add_edge("transit_latam_1", "transit_latam_2", latency=18.0, bandwidth_capacity=500.0, bidirectional=True)
    g.add_edge("transit_latam_2", "edge_7", latency=20.0, bandwidth_capacity=1000.0, bidirectional=True)
    g.add_edge("transit_latam_2", "edge_1", latency=85.0, bandwidth_capacity=300.0, bidirectional=True)

    # User 5 (S. Asia): user_5 -> transit_sasia_1 (10ms) -> transit_sasia_2 (12ms) -> edge_6 (Singapore, 16ms) = 3 HOPS (38ms)
    # Alternative failover: transit_sasia_1 -> transit_apac_1 (35ms)
    g.add_edge("user_5", "transit_sasia_1", latency=10.0, bandwidth_capacity=300.0, bidirectional=True)
    g.add_edge("transit_sasia_1", "transit_sasia_2", latency=12.0, bandwidth_capacity=500.0, bidirectional=True)
    g.add_edge("transit_sasia_2", "edge_6", latency=16.0, bandwidth_capacity=1000.0, bidirectional=True)
    g.add_edge("transit_sasia_1", "transit_apac_1", latency=35.0, bandwidth_capacity=300.0, bidirectional=True)

    return g


def generate_random_benchmark_graph(
    num_nodes: int,
    edge_density: float = 0.3,
    min_latency: float = 5.0,
    max_latency: float = 150.0,
    seed: Optional[int] = None,
) -> Graph:
    """Generate a connected random directed graph for empirical benchmarking.

    Guarantees at least a spanning backbone cycle to avoid disjoint components,
    then adds random edges up to edge_density.
    """
    if seed is not None:
        random.seed(seed)

    g = Graph()
    node_ids = [f"n_{i}" for i in range(num_nodes)]

    # Distribute node types: 1 origin, ~70% edge_servers, ~30% user_regions
    for idx, nid in enumerate(node_ids):
        if idx == 0:
            ntype = "origin"
        elif idx <= int(num_nodes * 0.7):
            ntype = "edge_server"
        else:
            ntype = "user_region"
        g.add_node(nid, node_type=ntype, label=f"Node {idx}")

    # Build initial spanning cycle
    for i in range(num_nodes):
        u = node_ids[i]
        v = node_ids[(i + 1) % num_nodes]
        lat = round(random.uniform(min_latency, max_latency), 2)
        g.add_edge(u, v, latency=lat)

    # Add random edges according to density
    for i in range(num_nodes):
        for j in range(num_nodes):
            if i != j and not g.has_edge(node_ids[i], node_ids[j]):
                if random.random() < edge_density:
                    lat = round(random.uniform(min_latency, max_latency), 2)
                    g.add_edge(node_ids[i], node_ids[j], latency=lat)

    return g


def generate_college_campus_topology() -> Graph:
    """Generate a college campus network topology with:
    - Admin Building (Origin · Central Campus Data Center)
    - AB1, AB2, AB3, AB4 (Academic Buildings 1 to 4 as Edge Servers)
    - Core Switch (IT Center Optical Transit)
    - Hostel Hub (Hostel Zone Distribution Hub)
    - Hostel Blocks A, B, C, D, E, F (User Regions / Residence Halls)
    """
    g = Graph()
    g.add_node("Admin", node_type="origin", label="Admin Building", tier="origin", role="Central Campus DC")
    g.add_node("AB1", node_type="edge_server", label="AB1 (Academic Building 1)", tier="edge", role="Academic Cluster 1")
    g.add_node("AB2", node_type="edge_server", label="AB2 (Academic Building 2)", tier="edge", role="Academic Cluster 2")
    g.add_node("AB3", node_type="edge_server", label="AB3 (Academic Building 3)", tier="edge", role="Academic Cluster 3")
    g.add_node("AB4", node_type="edge_server", label="AB4 (Academic Building 4)", tier="edge", role="Academic Cluster 4")
    g.add_node("Core_Switch", node_type="user_region", label="Core Switch (IT Center)", tier="transit")
    g.add_node("Hostel_Hub", node_type="user_region", label="Hostel Zone Distribution Hub", tier="transit")
    g.add_node("Hostel_A", node_type="user_region", label="Hostel Block A", tier="user")
    g.add_node("Hostel_B", node_type="user_region", label="Hostel Block B", tier="user")
    g.add_node("Hostel_C", node_type="user_region", label="Hostel Block C", tier="user")
    g.add_node("Hostel_D", node_type="user_region", label="Hostel Block D", tier="user")
    g.add_node("Hostel_E", node_type="user_region", label="Hostel Block E", tier="user")
    g.add_node("Hostel_F", node_type="user_region", label="Hostel Block F", tier="user")

    edges = [
        ("Admin", "Core_Switch", 1.0, 10000.0),
        ("Admin", "AB1", 1.2, 10000.0),
        ("Admin", "AB2", 1.5, 10000.0),
        ("Core_Switch", "AB3", 1.8, 5000.0),
        ("Core_Switch", "AB4", 1.6, 5000.0),
        ("AB1", "AB2", 1.4, 5000.0),
        ("AB2", "AB3", 1.6, 5000.0),
        ("AB3", "AB4", 1.5, 5000.0),
        ("AB4", "AB1", 2.0, 5000.0),
        ("Hostel_A", "AB1", 3.0, 1000.0),
        ("Hostel_A", "Hostel_B", 1.5, 1000.0),
        ("Hostel_B", "AB2", 3.2, 1000.0),
        ("Hostel_B", "Hostel_C", 1.6, 1000.0),
        ("Hostel_C", "AB2", 3.6, 1000.0),
        ("Hostel_C", "Hostel_D", 1.4, 1000.0),
        ("Hostel_D", "AB3", 3.4, 1000.0),
        ("Hostel_E", "AB4", 3.8, 1000.0),
        ("Hostel_E", "Hostel_F", 1.5, 1000.0),
        ("Hostel_F", "Hostel_Hub", 2.2, 1000.0),
        ("Hostel_Hub", "AB4", 2.8, 2000.0),
        ("Hostel_Hub", "AB3", 3.5, 2000.0),
    ]
    for u, v, lat, bw in edges:
        g.add_edge(u, v, latency=lat, bandwidth_capacity=bw, bidirectional=True)

    return g
