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
- **Status:** Complete (Tag: `m2`)
- **What was done:**
  - `services/topology_service.py`: JSON and two-CSV (nodes.csv + edges.csv) parser with row-numbered error reporting.
  - Enforced limits: max 200 nodes, 2000 edges, 1 MB file size.
  - Safe parsing without eval or pickle; validated unique IDs, edge node existence, positive capacity, structural node requirements (at least 1 origin, 1 edge_server, 1 user_region).
  - Warnings generated for negative latencies and disconnected nodes.
  - Session-scoped active topologies with automatic expiry and active topology name displayed in dashboard header.
  - Sample networks created in `samples/campus_network.json` and `samples/multi_region_cloud.json`.
  - Added REST endpoints: `POST /api/topology/upload`, `GET /api/topology/template`, `GET /api/topology/samples`, `POST /api/topology/load-sample`.
  - Dashboard UI updated with "Load Topology" modal, sample loaders, custom file upload, validation error feedback, and reset.
  - Tests: `tests/test_topology.py` covering valid JSON, valid CSVs, duplicate IDs, invalid types, missing nodes, negative capacity, missing origins, warnings, and templates (9 new tests).
  - Test suite: **35 passing tests** (original 20 untouched + 15 new).
- **How to verify:**
  - Run `pytest -v tests/test_topology.py tests/`
  - Start `python dashboard/app.py`, open `http://localhost:5000`, click "Load Topology", click "Campus Network" or "Multi-Region Cloud", and see active topology name update in header and canvas reload.
- **Known issues:** None.

---

## Milestone M3: LLM Layer, Agent, Chat UI
- **Status:** Pending
- **Scope:**
  - LLM client for OpenAI-compatible API configured by env vars + Fake provider
  - Tool-calling agent with JSON-schema tools for service functions, max 5 steps, Pydantic validation
  - Destructive tools confirmation safety check
  - Number grounding check: verify all numbers in response match tool results
  - Chat panel in dashboard with answer, expandable tools used, latency/tokens
  - Agent and number check unit tests
- **How to verify:** Pending
- **Known issues:** None.
