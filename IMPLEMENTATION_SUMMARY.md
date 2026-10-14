# Mini CDN Routing Simulator — Review 1 Implementation Summary

> **Course:** Design and Analysis of Algorithms (DAA)  
> **Project:** Mini CDN Routing Simulator (Review 1 — Foundation & Routing Engine)  
> **Status:** Fully Implemented, Validated, and Benchmarked

---

## 1. Executive Summary

This project implements a **Mini CDN Routing Simulator** that models how a Content Delivery Network (CDN) edge network makes optimal routing decisions. Designed specifically for **Review 1**, the implementation establishes the foundational network data model and routing algorithms, cross-validates their correctness, empirically analyzes their computational complexity, and demonstrates real-time dynamic rerouting via an interactive web dashboard.

All shortest-path routing engines are built **entirely from scratch** in Python without relying on external routing/graph libraries (e.g., NetworkX, SciPy) to meet strict academic and theoretical requirements.

---

## 2. Implemented Components Breakdown

### 2.1 Graph Data Model (`/graph`)
Located in [`graph/network.py`](file:///home/coded-x/Desktop/DAA_PROJ/graph/network.py) and [`graph/generator.py`](file:///home/coded-x/Desktop/DAA_PROJ/graph/generator.py):

* **`Node` Class**:
  * Node classification: `origin`, `edge_server`, `user_region`.
  * Support for hierarchical tiers (`origin`, `edge`, `user`, and `transit`).
  * Metadata tracking (regions, labels, coordinates, cache capacity).
* **`Edge` Class**:
  * Directed weighted links.
  * Weighted attributes: `latency` (ms) and `bandwidth_capacity` (Mbps).
* **`Graph` Class**:
  * Adjacency list representation supporting directed and bidirectional links.
  * Core graph operations:
    * `add_node(id, node_type, label, ...)`
    * `add_edge(u, v, latency, bandwidth_capacity, bidirectional)`
    * `remove_edge(u, v, bidirectional)` — **Link failure simulation**.
    * `update_edge_weight(u, v, latency, bandwidth_capacity)` — **Congestion simulation**.
    * `get_adjacency()` — returns adjacency weights for traversal.
    * `to_dict()` and `from_dict()` for JSON serialization with REST APIs.
* **Network Generators (`generator.py`)**:
  * **Realistic CDN Topology Generator**:
    * 1 Origin Server (Central DC).
    * 8 Edge Servers / POPs across global hubs (Virginia, Oregon, Frankfurt, Stockholm, Tokyo, Singapore, São Paulo, Cape Town).
    * Core peering mesh backbone with inter-edge links and cross-chords.
    * Access networks for 5 primary user regions.
    * Regional ISP/Transit Aggregation Relays (`transit_apac`, `transit_latam`, `transit_sasia`) guaranteeing **multi-hop (3+ hops)** routing demonstrations.
  * **Benchmark Graph Generator**:
    * Creates synthetic random connected graphs of size $N$ with customizable edge density for empirical benchmarking.

---

### 2.2 Routing Engine — Built From Scratch (`/routing`)

Located in [`routing/bellman_ford.py`](file:///home/coded-x/Desktop/DAA_PROJ/routing/bellman_ford.py) and [`routing/floyd_warshall.py`](file:///home/coded-x/Desktop/DAA_PROJ/routing/floyd_warshall.py):

#### A. Bellman-Ford (Single-Source Shortest Path — SSSP)
* **Theoretical Complexity**: $O(|V| \cdot |E|)$ time, $O(|V|)$ space.
* **Implementation Details**:
  * Runs $|V| - 1$ edge relaxation iterations over all edges.
  * **Negative Cycle Detection**: Executes a $|V|$-th iteration; raises `NegativeCycleException` if any edge can still be relaxed.
  * **Operation Instrumentation**: Counts each elementary edge relaxation comparison to enable hardware-independent empirical complexity evaluation.
  * Reconstructs the complete optimal path sequence from predecessor pointers.
  * Includes `find_best_edge_server_bf(graph, user_region_id)` to automatically locate the nearest, lowest-latency Edge POP.

#### B. Floyd-Warshall (All-Pairs Shortest Path — APSP)
* **Theoretical Complexity**: $O(|V|^3)$ time, $O(|V|^2)$ space.
* **Implementation Details**:
  * Dynamic programming triply-nested loop:
    $$D^{(k)}[i][j] = \min\left(D^{(k-1)}[i][j],\; D^{(k-1)}[i][k] + D^{(k-1)}[k][j]\right)$$
  * Predecessor / successor matrix tracking (`next_matrix`) for arbitrary $(u, v)$ path reconstruction.
  * **Negative Cycle Check**: Inspects diagonal entries ($D[i][i] < 0$).
  * **Operation Instrumentation**: Exactly counts all $|V|^3$ inner-loop comparisons.
  * Includes `find_best_edge_server_fw(graph, user_region_id)` leveraging the precomputed all-pairs matrix.

---

### 2.3 Correctness & Testing Suite (`/tests`)

20 automated unit tests implemented with `pytest` across 4 test modules:

1. **[`test_handcrafted.py`](file:///home/coded-x/Desktop/DAA_PROJ/tests/test_handcrafted.py)**:
   * 6-node hand-verifiable ground-truth network (`U1`, `E1`, `E2`, `E3`, `E4`, `O1`).
   * Asserts exact computed distances and path sequences against manual mathematical calculations.
2. **[`test_cross_validation.py`](file:///home/coded-x/Desktop/DAA_PROJ/tests/test_cross_validation.py)**:
   * Generates multiple topologies across varying random seeds and node sizes.
   * Cross-checks Bellman-Ford and Floyd-Warshall against each other; asserts 100% equivalence on lowest-latency edge selection, total path latency, and reconstructed paths.
3. **[`test_negative_cycle.py`](file:///home/coded-x/Desktop/DAA_PROJ/tests/test_negative_cycle.py)**:
   * Tests negative edge weights without cycles.
   * Asserts `NegativeCycleException` is raised by both algorithms on negative-weight cycles.
4. **[`test_graph.py`](file:///home/coded-x/Desktop/DAA_PROJ/tests/test_graph.py)**:
   * Tests node validation, edge addition, removal, weight updates, and multi-hop routing guarantees ($3+$ hops).

---

### 2.4 Empirical Benchmarking Suite (`/benchmarks`)

Located in [`benchmarks/benchmark.py`](file:///home/coded-x/Desktop/DAA_PROJ/benchmarks/benchmark.py):

* Generates random topologies of increasing size: $N \in [10, 20, 50, 80, 120, 160, 200]$.
* Runs multiple trials per $N$, measuring:
  * Wall-clock execution time (in milliseconds).
  * Measured elementary comparison/relaxation operation count.
* Exports results to:
  * [`benchmarks/results/benchmark_results.csv`](file:///home/coded-x/Desktop/DAA_PROJ/benchmarks/results/benchmark_results.csv)
  * [`benchmarks/results/complexity_benchmark.png`](file:///home/coded-x/Desktop/DAA_PROJ/benchmarks/results/complexity_benchmark.png) (Matplotlib plot showing measured vs. theoretical $O(V \cdot E)$ vs $O(V^3)$ curves on a logarithmic scale).

#### Summary Benchmark Results

| $|V|$ | $|E|$ | BF Time (ms) | BF Ops (Measured) | FW Time (ms) | FW Ops (Measured) | Theoretical $V^3$ |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **10** | 27 | 0.03 ms | 276 | 0.10 ms | 1,000 | 1,000 |
| **20** | 112 | 0.18 ms | 2,246 | 0.80 ms | 8,000 | 8,000 |
| **50** | 645 | 2.44 ms | 32,266 | 12.57 ms | 125,000 | 125,000 |
| **80** | 1,644 | 10.18 ms | 131,546 | 49.85 ms | 512,000 | 512,000 |
| **120** | 3,680 | 42.45 ms | 441,600 | 167.08 ms | 1,728,000 | 1,728,000 |
| **160** | 6,491 | 82.08 ms | 1,038,560 | 417.37 ms | 4,096,000 | 4,096,000 |
| **200** | 10,148 | 151.45 ms | 2,029,733 | 784.83 ms | 8,000,000 | 8,000,000 |

---

### 2.5 Interactive Web Dashboard (`/dashboard`)

Located in [`dashboard/app.py`](file:///home/coded-x/Desktop/DAA_PROJ/dashboard/app.py), [`dashboard/templates/index.html`](file:///home/coded-x/Desktop/DAA_PROJ/dashboard/templates/index.html), and [`dashboard/static/`](file:///home/coded-x/Desktop/DAA_PROJ/dashboard/static/):

* **Backend (Flask + REST API)**:
  * `GET /api/network`: Returns the graph formatted for Vis.js.
  * `POST /api/route`: Computes shortest paths using Bellman-Ford, Floyd-Warshall, or dual comparison mode.
  * `POST /api/network/kill-edge`: Simulates link failure by cutting a random link.
  * `POST /api/network/reset`: Restores the baseline network topology.
  * `GET /api/benchmark-data`: Returns benchmark metrics in JSON.
  * `GET /api/benchmark-image`: Serves the complexity benchmark visualization image.
* **Frontend UI Features**:
  * **Vis.js Interactive Graph Canvas**:
    * Color-coded nodes (Gold = Origin DC, Cyan = Edge POP, Teal = User Region, Purple = Transit Relay).
    * Edge weights shown on hover to prevent visual clutter; weights appear prominently along active routes.
    * Smooth ForceAtlas2 physics layout with "Fit View" centering.
  * **Click-to-Route & Multi-Hop Path Display**:
    * Clicking any user node displays the full route chain with directional badges (e.g. `User 3 ➔ Transit Ingress ➔ Transit Relay ➔ Edge 5`).
  * **Dual-Algorithm Cross-Validation View**:
    * "Compare Both" toggle runs Bellman-Ford and Floyd-Warshall concurrently, presenting a side-by-side card with an agreement checkmark (`✅ 100% Agreement`).
  * **Before / After Fault Adaptation Card**:
    * Clicking "⚡ Kill Random Edge" severs a link and displays a visual diff showing the severed prior path vs. new path and adaptation latency delta ($\Delta \text{ms}$).
  * **Embedded Benchmark Analytics Modal**:
    * "📊 Benchmark Analytics" button opens an in-app modal displaying the Matplotlib complexity chart and empirical metrics table.

---

## 3. Project Directory Structure

```
DAA_PROJ/
├── graph/                         # Graph data structures and topology generators
│   ├── __init__.py
│   ├── network.py                 # Node, Edge, and Graph classes
│   └── generator.py               # Hierarchical CDN & benchmark graph generators
├── routing/                       # Algorithmic routing engines from scratch
│   ├── __init__.py
│   ├── bellman_ford.py            # Bellman-Ford SSSP & negative cycle detection
│   └── floyd_warshall.py          # Floyd-Warshall APSP & path reconstruction
├── tests/                         # Comprehensive pytest test suite (20 tests)
│   ├── __init__.py
│   ├── test_graph.py              # Graph mutations and multi-hop guarantees
│   ├── test_handcrafted.py        # 6-node hand-calculated ground-truth verification
│   ├── test_cross_validation.py   # Dual-algorithm equivalence tests
│   └── test_negative_cycle.py     # Negative weight cycle handling
├── benchmarks/                    # Scalability and complexity benchmarks
│   ├── __init__.py
│   ├── benchmark.py               # Benchmark runner (N = 10 to 200)
│   └── results/
│       ├── benchmark_results.csv  # Empirical measurements
│       └── complexity_benchmark.png # High-res comparative complexity plot
├── dashboard/                     # Web visualization dashboard
│   ├── app.py                     # Flask backend and REST endpoints
│   ├── templates/
│   │   └── index.html             # Single-page dashboard interface
│   └── static/
│       ├── css/style.css          # Theme styles, modal, and diff card CSS
│       └── js/app.js              # Vis.js rendering, routing, and fault handling
├── requirements.txt               # Dependencies: flask, matplotlib, pytest
├── README.md                      # Full project documentation & execution guide
├── ROADMAP.md                     # Roadmap for subsequent phases (Max-Flow, Set Cover, etc.)
└── IMPLEMENTATION_SUMMARY.md      # Detailed record of all implemented features
```

---

## 4. Commands Reference

### Activate Environment
```bash
cd /home/coded-x/Desktop/DAA_PROJ
source .venv/bin/activate
```

### Run Automated Tests
```bash
pytest -v tests/
```

### Run Complexity Benchmarks
```bash
python benchmarks/benchmark.py
```

### Launch Web Dashboard
```bash
python dashboard/app.py
```
Open in browser: **`http://localhost:5000`**
