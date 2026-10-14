# NetPilot Extension Progress Tracking

This document tracks the progress of each milestone in the Mini CDN Routing Simulator NetPilot extension.

---

## Baseline (Review 1)
- **Status:** Complete (Tag: `baseline`)
- **What was done:**
  - Graph data model (`graph/network.py`, `graph/generator.py`)
  - Bellman-Ford SSSP with negative cycle detection (`routing/bellman_ford.py`)
  - Floyd-Warshall APSP with path reconstruction (`routing/floyd_warshall.py`)
  - 20 unit tests in `tests/` (100% passing)
  - Complexity benchmarks in `benchmarks/`
  - Interactive Flask + vis.js dashboard with Compare Both, fault simulation, and benchmark modal.

---

## Milestone M1: Max Flow, Service Layer, Event Store
- **Status:** Complete (Tag: `m1`)
- **What was done:**
  - `routing/max_flow.py`: Implemented Edmonds-Karp (BFS) and Ford-Fulkerson (DFS) with residual graph, super-sink, and min-cut analysis.
  - `storage/event_store.py`: SQLite-backed structured event store logging route computation, comparisons, failures, resets, what-if simulations, and max flow runs.
  - `services/network_service.py`: Pure functional service layer wrapping routing engines, flow calculations, what-if counterfactuals on graph copies, fault simulations, and metrics.
  - `dashboard/`:
    - Updated Flask backend to route through the service layer and log to the event store.
    - Added Max Flow panel with Edmonds-Karp, Ford-Fulkerson, and Compare Both side-by-side mode.
    - Integrated flow utilization labels on edges and highlighted bottleneck min-cut edges in bold red.
  - `tests/test_max_flow.py` and `tests/test_service_and_storage.py`: Handcrafted test, min-cut equivalence, disconnected sink, 50 random topologies NetworkX cross-validation, and service/storage tests.
  - Test suite: **26 passing tests** (original 20 untouched + 6 new).
- **How to verify:**
  - Run `pytest -v tests/`
  - Start app `python dashboard/app.py`, open `http://localhost:5000`, switch to "Max Flow & Min-Cut" tab, click "Compute Maximum Flow & Min-Cut", and observe flow labels and red min-cut edges.
- **Known issues:** None.

---

## Milestone M2: Topology Upload
- **Status:** Pending
- **Scope:**
  - Upload JSON or two CSVs (nodes.csv, edges.csv)
  - Row-numbered validation, constraints (200 nodes, 2000 edges, 1 MB), safe parsing
  - Per-session topology scoping with expiry, sample topologies in `/samples`, reset button
- **How to verify:** Pending
- **Known issues:** None.
