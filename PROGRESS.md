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
- **Status:** Complete (Tag: `m3`)
- **What was done:**
  - `copilot/llm_provider.py`: Implemented `OpenAICompatibleProvider` (using pure standard library `urllib.request` with no external OpenAI SDK dependency) and `FakeLLMProvider` (deterministic query routing for offline execution and fast testing). Reads `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL`.
  - `copilot/tools.py`: Implemented Pydantic argument models (`ShortestPathArgs`, `CompareAlgorithmsArgs`, `KillEdgeArgs`, `ResetNetworkArgs`, `WhatIfArgs`, `MaxFlowArgs`, `FindBottleneckArgs`, `GetMetricsArgs`, `ListNodesArgs`), OpenAI tool specifications, and dispatch execution into `services/network_service.py`.
  - `copilot/verifier.py`: Grounded number verification comparing every numeric token in LLM explanations against numbers produced in tool outputs (within 1% tolerance), automatically flagging any ungrounded figures.
  - `copilot/agent.py`: Agent loop with up to 5 tool steps, system prompt enforcing strict algorithmic grounding and active topology citations, destructive action confirmation gating for `kill_edge` and `reset_network`, and graceful offline response if `LLM_API_KEY` is unset.
  - `dashboard/`:
    - Added `POST /api/copilot/chat` endpoint supporting conversation history and action confirmation payloads.
    - Updated `index.html` and `style.css` with "NetPilot Copilot" button, slide-out chat drawer, suggestion chips, message bubbles, and expandable `<details>` tools used accordions.
    - Updated `static/js/app.js` with chat communication, message history rendering, expandable tool execution inspector, grounding status badge, and interactive confirmation button for destructive actions.
  - `tests/test_copilot.py`: 7 tests covering Fake provider query mapping, Pydantic schema validation, destructive confirmation gate, number grounding verification, agent loop what-if execution, and Flask API endpoint.
  - Test suite: **42 passing tests** (original 20 untouched + 22 new).
- **How to verify:**
  - Run `pytest -v tests/test_copilot.py tests/`
  - Start `python dashboard/app.py`, open `http://localhost:5000`, click "🤖 NetPilot Copilot", click quick prompt chips or ask natural language queries.
- **Known issues:** None.

---

## Milestone M4: Deployment Baseline & Guardrails
- **Status:** Complete (Tag: `m4`)
- **What was done:**
  - `Dockerfile`: Multi-stage build with `python:3.12-slim`, non-root system user (`cdnapp`), minimal dependencies, and built-in health check polling `http://localhost:5000/api/network`.
  - `docker-compose.yml`: Configured single-command deployment with volume persistence for the SQLite event store (`network_events.db`).
  - `.env.example`: Fully documented environment variables for `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `EMBED_MODEL`, `COPILOT_ENABLED`, `RATE_LIMIT_PER_MINUTE`, and `DAILY_TOKEN_BUDGET`.
  - `.github/workflows/ci.yml`: GitHub Actions automated CI testing workflow running on push/PR for Python 3.12.
  - `copilot/guardrails.py`:
    - Sliding 60-second window rate limiter (default 10 req/min per session, returns 429 with `Retry-After`).
    - UTC calendar-day token budget tracker (default 100,000 tokens, returns 429 upon exhaustion).
    - Administrative kill switch (`COPILOT_ENABLED=false` returning 503 while preserving normal routing operations).
  - `dashboard/app.py`: Integrated guardrails into `POST /api/copilot/chat`.
  - `README.md`: Added comprehensive Deployment section covering local Docker run, Docker Compose, Render, Fly.io, and Hugging Face Spaces.
  - `tests/test_deployment_and_limits.py`: 4 tests for rate limiting, token budget enforcement, kill switch, and HTTP 429/503 headers.
  - Test suite: **46 passing tests** (original 20 untouched + 26 new).
- **How to verify:**
  - Run `pytest -v tests/test_deployment_and_limits.py tests/`
  - Inspect `.env.example`, `Dockerfile`, and `docker-compose.yml`.
- **Known issues:** None.

---

## Milestone M5: RAG Over History and Runbooks
- **Status:** Complete (Tag: `m5`)
- **What was done:**
  - `rag/embedder.py`: Configured embedding provider supporting `EMBED_MODEL` (e.g. `text-embedding-3-small` via standard library `urllib.request`) and a `DeterministicFakeEmbedder` that produces normalized vectors with semantic cluster weighting for reliable offline execution and unit testing.
  - `rag/vector_store.py`: In-memory and SQLite-backed vector store using table `documents(id, doc_type, title, content, chunk_path, embedding_json)` with pure Python cosine similarity (zero external vector database dependency).
  - `runbooks/`: 5 operational runbooks chunked by Markdown headings with explicit chunk paths:
    - `link_failure_runbook.md` (Isolating severed links, rerouting traffic, verifying latency)
    - `congestion_runbook.md` (Detecting saturated links, min-cut analysis, traffic throttling)
    - `regional_outage_runbook.md` (Cascading POP failures, regional failover, user rehoming)
    - `latency_regression_runbook.md` (Diagnosing multi-hop detours, algorithm cross-verification)
    - `bad_topology_upload_runbook.md` (Identifying broken uploads, rollback to baseline CDN)
  - `copilot/tools.py`: Added tool `search_history` with Pydantic validation schema `SearchHistoryArgs` to retrieve relevant runbooks and recent synced events.
  - `copilot/agent.py`: Wrapped retrieved chunks in strict isolation delimiters (`=== RETRIEVED CONTEXT === ... === END RETRIEVED CONTEXT ===`) and added prompt instructions to prevent prompt injection and system prompt leaks.
  - `copilot/verifier.py`: Added `verify_event_id_grounding` to detect fabricated event ID citations and flag them with verification warnings.
  - `tests/test_rag.py`: 5 tests covering fake embedder normalization, runbook chunking & retrieval, event sync, prompt injection delimiter isolation, and event citation verification.
  - Test suite: **51 passing tests** (original 20 untouched + 31 new).
- **How to verify:**
  - Run `pytest -v tests/test_rag.py tests/`
  - Start `python dashboard/app.py`, open `http://localhost:5000`, open Copilot drawer, and ask "What is the runbook procedure for link failure?"
- **Known issues:** None.

---

## Milestone M6: Incident Postmortem Generator
- **Status:** Complete (Tag: `m6`)
- **What was done:**
  - `services/postmortem_service.py`: Generates structured Markdown incident postmortems for network failure/outage events containing:
    1. Summary (Incident identifier, timestamp, affected topology, target link)
    2. Chronological Timeline (surrounding events table with timestamps, event types, compute durations)
    3. Impact Assessment (affected communication link, baseline vs post-incident latency, delta ms, hop progression)
    4. Root Cause Analysis (link severance details, shortest-path dynamic rerouting explanation)
    5. Preventative Mitigations (topology redundancy, capacity headroom, runbook references)
  - All numbers, hops, and event IDs are strictly sourced from SQLite event store telemetry and verified by grounding validators.
  - `copilot/tools.py`: Registered `generate_postmortem` tool with Pydantic schema `GeneratePostmortemArgs`.
  - `dashboard/app.py`: Added `POST /api/postmortem/generate` endpoint.
  - `dashboard/templates/index.html` & `dashboard/static/js/app.js`:
    - Added "📋 Generate Incident Postmortem" button in Fault Simulation panel that reveals after a failure occurs.
    - Added interactive Postmortem Modal with syntax-highlighted preview and "⬇️ Download .md" button to export report directly.
  - `tests/test_postmortem.py`: 4 tests for report sections, number grounding verification, event citation grounding, and Flask API endpoint.
  - Test suite: **55 passing tests** (original 20 untouched + 35 new).
- **How to verify:**
  - Run `pytest -v tests/test_postmortem.py tests/`
  - Start `python dashboard/app.py`, open `http://localhost:5000`, click "⚡ Kill Random Edge", then click "📋 Generate Incident Postmortem" to inspect the synthesized report and click "⬇️ Download .md".
- **Known issues:** None.



