# Project Roadmap: Mini CDN System & NetPilot

> **Course:** Design and Analysis of Algorithms (DAA)  
> **Status:** Review 1 & Review 2 Completed

---

## Architecture Evolution

```
+-------------------------------------------------------------------------+
|                  Mini CDN Distributed Routing Platform                  |
+-------------------------------------------------------------------------+
                                    │
     ┌──────────────────────────────┼──────────────────────────────┐
     │                              │                              │
[Completed - Review 1]        [Completed - Review 2]         [Future Stretch Goals]
Routing Foundation            NetPilot Autonomous AI         Advanced Algorithms
- Directed Graph Model        - Edmonds-Karp Max Flow        - Live Mode (ICMP / Traceroute)
- Bellman-Ford (SSSP)         - Ford-Fulkerson Flow (DFS)    - Karger's Randomized Min-Cut
- Floyd-Warshall (APSP)       - Super-Sink & Min-Cut         - Greedy Set Cover Edge Placement
- Negative Cycle Detection    - RAG Operational Runbooks     - Consistent Hashing Content Router
- Empirical Benchmarks        - Grounding Verifiers          - Multi-Agent Autonomous SRE
- Vis.js Dark Dashboard       - Postmortem & Mitigations
                              - Offline Evaluation Harness
```

---

## Detailed Milestone Status

### Review 1: Core Routing Engine (Completed)
- [x] **Directed Weighted Graph Model**: Custom Node, Edge, and Graph data structures with dynamic link failure (`remove_edge`) and congestion (`update_edge_weight`).
- [x] **Bellman-Ford SSSP (from scratch)**: Arbitrary weight support, negative-weight cycle detection, and operation counters tracking theoretical $O(V \cdot E)$.
- [x] **Floyd-Warshall APSP (from scratch)**: Dynamic programming matrix computation with path reconstruction and operation counters tracking theoretical $O(V^3)$.
- [x] **Cross-Validation Suite**: Handcrafted 6-node ground-truth assertions and automated cross-validation on 50 random topologies.
- [x] **Interactive Dashboard**: Vis.js canvas with shortest-path rendering, multi-hop routing demonstrations, fault injection, and benchmark viewer.

### Review 2: NetPilot AI Copilot, Max Flow & LLMOps (Completed)
- [x] **Milestone M1 — Max Flow & Min-Cut Engine**:
  - Edmonds-Karp (BFS augmenting paths on residual graph $G_f$, $O(V \cdot E^2)$).
  - Ford-Fulkerson (DFS augmenting paths, $O(E \cdot |f^*|)$).
  - Multi-sink routing via virtual super-sink.
  - Min-cut bottleneck capacity and cut edge discovery.
  - SQLite persistent event store (`network_events.db`).
- [x] **Milestone M2 — User Topologies & Validation**:
  - JSON & CSV topology parser supporting up to 200 nodes / 2000 edges.
  - Structural validation with row-numbered error messages.
  - Prebuilt sample topologies: Campus LAN, Cloud Multi-Region, Hierarchical CDN.
- [x] **Milestone M3 — NetPilot AI Copilot Architecture**:
  - ReAct agent loop (5 iterations max) with OpenAI-compatible API and offline `FakeLLMProvider`.
  - Pydantic schema validation for all copilot tools (`shortest_path`, `compare_algorithms`, `what_if`, `max_flow`, `find_bottleneck`).
  - Destructive action confirmation gates (`kill_edge`, `reset_network`).
  - Number grounding verifier ensuring answers contain only verified tool outputs.
- [x] **Milestone M4 — Guardrails & Production Deployment**:
  - In-memory sliding-window rate limiter (10 req/min per session).
  - UTC daily token budget manager (100k tokens/day).
  - Master kill switch (`COPILOT_ENABLED`).
  - Multi-stage Dockerfile, docker-compose, and GitHub Actions CI.
- [x] **Milestone M5 — RAG Runbooks & History Search**:
  - SQLite vector store with pure Python cosine similarity search.
  - 5 operational markdown runbooks chunked and indexed.
  - Strict delimiter isolation (`=== RETRIEVED CONTEXT ===`) to prevent prompt injections.
  - Event ID citation grounding verifier.
- [x] **Milestone M6 — Incident Postmortem Generator**:
  - Automated structured Markdown postmortem generator (Summary, Timeline, Impact, Root Cause, Mitigations).
  - Strictly grounded in SQLite event store telemetry; exportable as `.md`.
- [x] **Milestone M7 — Propose, Simulate, Verify Mitigations**:
  - Isolated graph copy simulation (`graph.clone()`) leaving live graph 100% untouched.
  - Discarding of invalid candidates and deterministic ranking by measured empirical metric deltas.
  - User confirmation gate before applying mitigations to the active network.
- [x] **Milestone M8 — Evaluation Harness & LLMOps Panel**:
  - 50 programmatic questions (15 dev, 35 test) evaluated across 4 configurations (Plain LLM, LLM+RAG, LLM+Tools, Full NetPilot) over 3 runs (420 test queries).
  - Scoring rules: 1% numeric tolerance, exact integer/set match, runbook citation check, destructive action gate check.
  - Hallucination tracking across all configurations.
  - LLMOps Dashboard Panel (`GET /api/llmops/stats`, token budget gauge, runbook coverage, and sanitized audit log).

### Extensions: Advanced Engines & Resilience (Milestones X1 - X3) (Completed)
- [x] **Milestone X1 — Dijkstra SSSP Engine & Binary Min-Heap**:
  - Hand-written Dijkstra algorithm using standard library binary min-heap (`heapq`).
  - Negative edge guard raising explicit `ValueError` on negative weights.
  - 3-way shortest path agreement badge (`Compare Both`) validating Bellman-Ford == Floyd-Warshall == Dijkstra.
  - Scalability benchmarks ($N=10..200$) and apples-to-apples All-Pairs Dijkstra vs. Floyd-Warshall.
- [x] **Milestone X2 — Step-Through Algorithmic Visualizer**:
  - Detailed step trace recording for Bellman-Ford passes and Floyd-Warshall intermediate pivots.
  - Dashboard playback panel with Play/Pause, Step Next, Step Prev, and speed controls.
  - Dynamic Vis.js edge highlighting and real-time distance delta table inspection.
- [x] **Milestone X3 — Chaos Mode & Autonomous Self-Healing**:
  - Background daemon periodically injecting random link/node failures at configurable intervals.
  - Automated postmortem generation triggered on cascading failure thresholds.
  - Auto-heal and reset engine restoring topologies to pristine baseline.

---

## Future Stretch Goals (Post-Review 2)

### 1. Live Mode (Real-World Network Probing)
- Integrate ICMP ping and traceroute against live IP addresses or public DNS endpoints (e.g., 1.1.1.1, 8.8.8.8).
- Dynamically convert real-world RTT latency measurements into edge weights on an active geographic topology map.
- Demonstrate automatic rerouting when live packet loss or latency spikes occur in real time.

### 2. Karger's Randomized Min-Cut Algorithm
- Implement Karger's contraction algorithm from scratch in pure Python.
- Compare randomized contraction against the deterministic Edmonds-Karp reachability min-cut:
  - Benchmark execution times across dense graphs.
  - Analyze the empirical probability of finding the global minimum cut vs iteration count $T = O(V^2 \log V)$.

### 3. Greedy Set Cover for Optimal Edge POP Placement
- Formulate the CDN Edge Server Placement problem as a **Weighted Set Cover** problem:
  - Given a set of user regions requiring coverage within latency threshold $L_{\max}$, select the minimum-cost subset of edge POPs that covers all regions.
  - Implement the $(1 + \ln |U|)$-approximation greedy algorithm and compare against brute-force optimal on small topologies.
