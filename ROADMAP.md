# Project Roadmap: Mini CDN System

> **Course:** Design and Analysis of Algorithms (DAA)  
> **Status:** Review 1 (Phase 1) Completed

---

## Architecture Evolution

```
+-------------------------------------------------------------------------+
|                  Mini CDN Distributed Routing Platform                  |
+-------------------------------------------------------------------------+
                                    |
     +------------------------------+------------------------------+
     |                              |                              |
[Completed]                    [Phase 2]                      [Phase 3 & 4]
Review 1: Routing Engine       Review 2: Flow & Bandwidth     Review 3: Caching & Load
- Directed Graph Model         - Ford-Fulkerson (DFS)         - Greedy Set Cover
- Bellman-Ford (SSSP)          - Edmonds-Karp (BFS)           - Consistent Hashing
- Floyd-Warshall (APSP)        - Max Bandwidth Allocation     - Randomized Load Balancing
- Negative Cycle Detection     - Residual Graphs & Cuts       - Global Edge Orchestrator
- Empirical Benchmarks         - Bottleneck Edge Detection
```

---

## Detailed Phase Breakdown

### Phase 1: Core Routing Foundation (Review 1 - CURRENT)
- [x] **Directed Weighted Graph**: Node types (`origin`, `edge_server`, `user_region`), failure simulation via `remove_edge`, and congestion updates via `update_edge_weight`.
- [x] **Bellman-Ford SSSP (from scratch)**: Arbitrary weight handling, relaxation over $|V|-1$ passes, negative-weight cycle detection, and empirical operation counters.
- [x] **Floyd-Warshall APSP (from scratch)**: All-pairs distance and path reconstruction matrices with $O(V^3)$ comparisons tracking.
- [x] **Correctness & Cross-Validation**: Hand-calculated 6-node ground-truth assertions, cross-algorithm validation on random topologies, and negative cycle validation.
- [x] **Empirical Benchmarking**: Scalability analysis across $N \in [10, 200]$ validating theoretical $O(V \cdot E)$ vs $O(V^3)$ curves via CSV and matplotlib visualizations.
- [x] **Interactive Dashboard**: Vis.js network visualization, click-to-route path tracing, dynamic link failure simulation, and live telemetry.

---

### Phase 2: Bandwidth Constraints & Maximum Flow (Review 2)
*Focus: Ensuring network links can support client demand volumes without saturation.*

- [ ] **Capacity-Constrained Edge Model**:
  - Augment edges with capacity $c(u, v)$ and flow $f(u, v)$.
- [ ] **Ford-Fulkerson Algorithm (Augmenting Paths via DFS)**:
  - Theoretical complexity: $O(E \cdot |f^*|)$.
  - Residual graph construction $G_f$ with forward and backward edges.
- [ ] **Edmonds-Karp Algorithm (Shortest Augmenting Path via BFS)**:
  - Theoretical complexity: $O(V \cdot E^2)$.
  - Prevents pathological flow augmentations on irrational or high-capacity links.
- [ ] **Minimum Cut & CDN Bottleneck Identification**:
  - By the Max-Flow Min-Cut Theorem, identify the exact bottleneck links between origin servers and edge POP clusters.
- [ ] **Empirical Flow Comparison**:
  - Benchmark DFS augmenting path selection vs BFS (Edmonds-Karp) across varying flow demands.

---

### Phase 3: Edge Cache Placement via Set Cover (Review 3)
*Focus: Optimal geographical placement of edge servers and content replicates.*

- [ ] **Set Cover Formulation**:
  - Given a universe of user regions $U = \{u_1, u_2, \dots, u_m\}$ and candidate edge cache POPs with defined coverage radii (e.g. latency $\le 30\text{ms}$).
  - Objective: Minimize deployed edge servers while covering 100% of user populations.
- [ ] **Greedy Approximation Algorithm**:
  - $H_n$-factor logarithmic approximation ratio: $O(\ln |U|)$.
- [ ] **Branch-and-Bound / Integer Linear Programming (ILP) Comparison**:
  - Contrast greedy heuristic with optimal exhaustive branch-and-bound for small $N$.

---

### Phase 4: Dynamic Load Balancing & Consistent Hashing (Final Evaluation)
*Focus: Preventing edge server over-utilization under skewed client traffic.*

- [ ] **Consistent Hashing Ring**:
  - Implementation with virtual nodes (vnodes) to balance user requests across edge servers with $O(\log S)$ lookup.
- [ ] **Randomized Load Balancing (Power of Two Choices)**:
  - Route each incoming request to $\min(\text{load}(e_i), \text{load}(e_j))$ to achieve $O(\log \log n)$ maximum queue length.
- [ ] **End-to-End Unified CDN Simulator**:
  - Integrated simulation: Request routing (Phase 1) $\rightarrow$ Bandwidth allocation (Phase 2) $\rightarrow$ Cache placement (Phase 3) $\rightarrow$ Dynamic load balancing (Phase 4).
