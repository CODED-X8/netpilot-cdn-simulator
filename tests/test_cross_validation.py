"""Cross-validation test suite comparing Bellman-Ford and Floyd-Warshall outputs."""

import pytest
from graph.generator import generate_cdn_topology, generate_random_benchmark_graph
from routing.bellman_ford import bellman_ford, find_best_edge_server_bf
from routing.floyd_warshall import floyd_warshall, find_best_edge_server_fw


@pytest.mark.parametrize("seed", [10, 42, 99])
def test_cross_validation_cdn_topology(seed: int):
    """Assert Bellman-Ford and Floyd-Warshall produce identical shortest distances on CDN topologies."""
    g = generate_cdn_topology(num_origins=1, num_edges=8, num_users=5, seed=seed)
    fw = floyd_warshall(g)

    # Validate all user regions to all edge servers
    user_nodes = g.get_nodes_by_type("user_region")
    edge_nodes = g.get_nodes_by_type("edge_server")

    for user in user_nodes:
        bf = bellman_ford(g, user.id)

        # Cross-check best edge server selection
        best_bf = find_best_edge_server_bf(g, user.id)
        best_fw = find_best_edge_server_fw(g, user.id, fw)

        assert best_bf["best_edge"] == best_fw["best_edge"]
        assert pytest.approx(best_bf["latency"], rel=1e-5) == best_fw["latency"]

        for edge in edge_nodes:
            bf_dist = bf.distances.get(edge.id, float("inf"))
            fw_dist = fw.get_distance(user.id, edge.id)

            if bf_dist == float("inf"):
                assert fw_dist == float("inf")
            else:
                assert pytest.approx(bf_dist, rel=1e-5) == fw_dist

                # Validate reconstructed paths have matching total weight
                bf_path = bf.get_path(edge.id)
                fw_path = fw.get_path(user.id, edge.id)

                assert bf_path is not None
                assert fw_path is not None
                assert bf_path[0] == user.id and bf_path[-1] == edge.id
                assert fw_path[0] == user.id and fw_path[-1] == edge.id

                # Calculate sum of edge weights along paths
                def path_cost(p):
                    cost = 0.0
                    for i in range(len(p) - 1):
                        cost += g.get_edge(p[i], p[i + 1]).latency
                    return cost

                assert pytest.approx(path_cost(bf_path), rel=1e-5) == bf_dist
                assert pytest.approx(path_cost(fw_path), rel=1e-5) == fw_dist


@pytest.mark.parametrize("n_nodes", [8, 15, 25])
def test_cross_validation_random_dense_graphs(n_nodes: int):
    """Assert Bellman-Ford and Floyd-Warshall match on dense random graphs."""
    g = generate_random_benchmark_graph(num_nodes=n_nodes, edge_density=0.4, seed=123)
    fw = floyd_warshall(g)

    nodes = list(g.nodes.keys())
    # Sample 5 source nodes to cross-validate
    for src in nodes[:5]:
        bf = bellman_ford(g, src)
        for dst in nodes:
            bf_d = bf.distances[dst]
            fw_d = fw.get_distance(src, dst)
            if bf_d == float("inf"):
                assert fw_d == float("inf")
            else:
                assert pytest.approx(bf_d, rel=1e-5) == fw_d
