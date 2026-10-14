# Mini CDN Routing Simulator (DAA Course Project — Review 1)

A simulator modeling how Content Delivery Networks (CDNs) make optimal edge routing decisions using fundamental graph algorithms implemented from scratch in Python.

---

## 📌 Context & Scope (Review 1)

Modern CDNs (e.g., Cloudflare, Akamai, Fastly) route incoming user traffic across a distributed topology composed of **Origin Servers**, **Edge POP Servers**, and **User Regions**. Communication links are characterized by **Latency** (ms) and **Bandwidth Capacity** (Mbps).

In this foundational phase (Review 1), the system implements and cross-validates two classic shortest-path routing algorithms from scratch:
1. **Bellman-Ford Algorithm** (Single-Source Shortest Path — SSSP)
2. **Floyd-Warshall Algorithm** (All-Pairs Shortest Path — APSP)

Neither library calls (e.g., NetworkX, SciPy) nor prebuilt graph frameworks are used for the routing engines. Both algorithms are instrumented with **elementary operation counters** to empirically validate their theoretical asymptotic complexities ($O(V \cdot E)$ vs $O(V^3)$).

---

## 🏗️ Repository Architecture

```
DAA_PROJ/
├── graph/                      # Directed graph data model & generators
│   ├── __init__.py
│   ├── network.py              # Node, Edge, and Graph data structures
│   └── generator.py            # Hierarchical CDN & random benchmark topologies
├── routing/                    # Core algorithmic routing engines (from scratch)
│   ├── __init__.py
│   ├── bellman_ford.py         # Bellman-Ford SSSP with negative cycle detection
│   └── floyd_warshall.py       # Floyd-Warshall APSP with path reconstruction
├── tests/                      # Automated validation suite (pytest)
│   ├── __init__.py
│   ├── test_graph.py           # Graph operations & mutation tests
│   ├── test_handcrafted.py     # 6-node hand-calculated ground-truth verification
│   ├── test_cross_validation.py# Cross-algorithm assertions across topologies
│   └── test_negative_cycle.py  # Negative cycle detection assertions
├── benchmarks/                 # Empirical complexity benchmarking suite
│   ├── __init__.py
│   ├── benchmark.py            # Benchmark runner (N = 10 to 200)
│   └── results/
│       ├── benchmark_results.csv   # Empirical metrics (wall-clock time, ops)
│       └── complexity_benchmark.png# Publication-quality complexity plots
├── dashboard/                  # Interactive visual dashboard
│   ├── app.py                  # Flask web backend & REST API
│   ├── templates/
│   │   └── index.html          # Interactive interface
│   └── static/
│       ├── css/style.css       # Clean dark-mode stylesheet
│       └── js/app.js           # Vis.js network rendering & dynamic rerouting
├── requirements.txt            # Minimal runtime dependencies (Flask, Matplotlib, Pytest)
├── ROADMAP.md                  # Stubs for future phases (Max-Flow, Set Cover, Load Balancing)
└── README.md                   # Complete documentation & execution guide
```

---

## ⚙️ Algorithms & Theoretical Complexity

| Metric / Property | Bellman-Ford Algorithm | Floyd-Warshall Algorithm |
| :--- | :--- | :--- |
| **Scope** | Single-Source Shortest Path (SSSP) | All-Pairs Shortest Path (APSP) |
| **Time Complexity** | $O(|V| \cdot |E|)$ | $O(|V|^3)$ |
| **Space Complexity** | $O(|V|)$ | $O(|V|^2)$ |
| **Edge Weights** | Arbitrary real numbers | Arbitrary real numbers |
| **Negative Cycle Handling** | Detects cycles reachable from source via $|V|$-th pass | Detects cycles via negative diagonal entries $D[i][i] < 0$ |
| **Path Reconstruction** | Predecessor map $\pi[v]$ | Successor/intermediate matrix $\text{next}[i][j]$ |
| **Use Case in CDN** | On-demand path finding from a specific user region to candidate POPs | Global routing table precomputation across all nodes in the CDN backbone |

### 1. Bellman-Ford Algorithm
- Iteratively relaxes all directed edges $|V| - 1$ times.
- On the $|V|$-th iteration, if any edge can still be relaxed, a **negative-weight cycle** exists.
- In `routing/bellman_ford.py`, this raises a specialized `NegativeCycleException`.
- Each relaxation comparison increments the internal operation counter by 1.

### 2. Floyd-Warshall Algorithm
- Employs dynamic programming using the recurrence:
  $$D^{(k)}[i][j] = \min\left(D^{(k-1)}[i][j],\; D^{(k-1)}[i][k] + D^{(k-1)}[k][j]\right)$$
- Tracks a companion predecessor/next matrix:
  $$\text{next}[i][j] = \text{next}[i][k] \quad \text{when } D[i][k] + D[k][j] < D[i][j]$$
- Operates in three nested loops from $0$ to $|V|-1$, producing strictly $|V|^3$ elementary comparisons.

---

## 🚀 Quickstart & Setup

### 1. Environment Setup
Clone or navigate to the repository directory and create a virtual environment:

```bash
# Navigate to project root
cd /home/coded-x/Desktop/DAA_PROJ

# Create Python virtual environment
python3 -m venv .venv

# Activate environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

### 2. Running Automated Tests
Run the comprehensive test suite with `pytest`:

```bash
pytest -v tests/
```

**What is tested:**
- `test_graph.py`: Graph edge addition, node classifications, edge removal (failure simulation), and weight updates (congestion simulation).
- `test_handcrafted.py`: A hand-calculated 6-node topology where shortest paths and distances are verified against exact mathematical ground truth.
- `test_cross_validation.py`: Asserts that Bellman-Ford and Floyd-Warshall yield identical distance matrices and optimal edge selections on random topologies.
- `test_negative_cycle.py`: Verifies that both algorithms correctly identify negative-weight cycles and raise `NegativeCycleException`.

---

### 3. Running Complexity Benchmarks
Execute the empirical benchmark script to test graph sizes from $N=10$ to $N=200$:

```bash
python benchmarks/benchmark.py
```

Outputs generated:
- `benchmarks/results/benchmark_results.csv`: Measured wall-clock execution times and operation counts.
- `benchmarks/results/complexity_benchmark.png`: High-resolution dual-panel matplotlib chart comparing empirical vs theoretical scaling.

#### Empirical Benchmark Results Table:
| $|V|$ (Nodes) | $|E|$ (Edges) | Bellman-Ford Time (ms) | Bellman-Ford Ops | Floyd-Warshall Time (ms) | Floyd-Warshall Ops |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **10** | 27 | 0.03 ms | 276 | 0.10 ms | 1,000 |
| **20** | 112 | 0.18 ms | 2,246 | 0.80 ms | 8,000 |
| **50** | 645 | 2.44 ms | 32,266 | 12.57 ms | 125,000 |
| **80** | 1,644 | 10.18 ms | 131,546 | 49.85 ms | 512,000 |
| **120** | 3,680 | 42.45 ms | 441,600 | 167.08 ms | 1,728,000 |
| **160** | 6,491 | 82.08 ms | 1,038,560 | 417.37 ms | 4,096,000 |
| **200** | 10,148 | 151.45 ms | 2,029,733 | 784.83 ms | 8,000,000 |

*Notice:* Floyd-Warshall operations scale precisely as $N^3$ ($200^3 = 8\times 10^6$), while Bellman-Ford scales strictly with $V \cdot E$.

---

### 4. Running the Interactive Dashboard
Launch the interactive Flask visualization dashboard:

```bash
python dashboard/app.py
```

Then open your browser and navigate to:
```
http://localhost:5000
```

#### Dashboard Features:
1. **Interactive Topology Visualization (Vis.js)**:
   - Gold Diamonds: Origin Data Centers
   - Cyan Hexagons: Edge POP Servers
   - Teal Circles: User Population Regions
   - Edge labels indicate latency in milliseconds.
2. **Click-to-Route**: Click any teal User Region node to immediately compute the shortest path to the lowest-latency Edge POP.
3. **Algorithm Switching**: Toggle between Bellman-Ford and Floyd-Warshall to see empirical comparison of execution times and operation counts side-by-side.
4. **Failure Simulation ("Kill Random Edge")**: Click the button to sever an active communication link. The system dynamically detects the failure, re-runs routing, and highlights the updated alternative path in real time.
5. **Network Reset**: Instantly restores the network to baseline topology.

---

## 🎯 Review 1 Presentation Guide (Key Talking Points)

1. **Academic Rigor**: Emphasize that all algorithms were written from scratch with no third-party routing libraries used.
2. **Cross-Validation**: Explain how `test_handcrafted.py` verifies mathematical ground truth, while `test_cross_validation.py` asserts algorithm equivalence across randomized topologies.
3. **Empirical vs Theoretical**: Present `complexity_benchmark.png` and explain how measuring atomic comparisons directly validates asymptotic Big-$O$ bounds independently of hardware noise.
4. **CDN Problem Formulation**: Highlight that the goal is solving nearest-edge discovery for client populations rather than generic arbitrary routing.
5. **Extensibility**: Reference [ROADMAP.md](ROADMAP.md) to show how Review 1 lays the foundation for Maximum Flow (Review 2), Set Cover Caching (Review 3), and Dynamic Load Balancing (Final).
