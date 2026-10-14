# Mini CDN Routing Simulator & NetPilot AI Copilot

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests: 66 Passed](https://img.shields.io/badge/tests-66%20passed-brightgreen.svg)]()
[![Docker: Ready](https://img.shields.io/badge/docker-multi--stage-blue.svg)]()

A high-performance simulator and autonomous AI Copilot system modeling how Content Delivery Networks (CDNs) make optimal edge routing, capacity allocation, fault recovery, and incident mitigation decisions. Built for the **Design and Analysis of Algorithms (DAA)** curriculum.

All core graph routing, network flow, and simulation engines are implemented **completely from scratch in pure Python** with **zero external routing libraries** (NetworkX is restricted strictly to cross-validation tests).

---

## 🌟 Key Capabilities

### 1. Core Algorithmic Routing Engine (Review 1)
- **Bellman-Ford (Single-Source Shortest Path)**: Relaxations over $|V|-1$ passes, negative-weight cycle detection, and operation counters validating theoretical $O(|V| \cdot |E|)$.
- **Floyd-Warshall (All-Pairs Shortest Path)**: Dynamic programming matrix computation with predecessor path reconstruction and operation counters validating theoretical $O(|V|^3)$.
- **Empirical Benchmarking Suite**: Automated scalability analysis across $N \in [10, 200]$ with generated publication-quality plots.
- **Interactive Dark Dashboard**: Vis.js force-directed canvas with multi-hop route highlighting, latency/hop metrics, and link failure simulation.

### 2. Network Flow & Max Flow Engine (Review 2)
- **Edmonds-Karp Algorithm**: Shortest augmenting path discovery via Breadth-First Search (BFS) on residual graph $G_f$ in $O(|V| \cdot |E|^2)$.
- **Ford-Fulkerson Algorithm**: Depth-First Search (DFS) augmenting path algorithm for theoretical comparison.
- **Multi-Sink Flow Allocation**: Virtual super-sink routing simultaneously delivering traffic from origin to all edge servers.
- **Min-Cut Bottleneck Theorem**: Identifies exact capacity-limiting cut edges and total min-cut bandwidth.

### 3. NetPilot Autonomous AI Copilot (Review 2)
- **Zero-Hallucination ReAct Architecture**: The LLM *never* computes routes, flows, or metrics in its head. It calls deterministic Python tools wrapping our custom engines and explains the tool outputs.
- **Anti-Hallucination Grounding Verifiers**:
  - **Number Grounding Verifier**: Regex validation ensuring every number in the LLM's answer is mathematically grounded in tool outputs within 1% tolerance.
  - **Event ID Citation Verifier**: Ensures incident citations exist in SQLite event store telemetry.
- **Destructive Confirmation Gate**: Actions that mutate live networks (`kill_edge`, `reset_network`, `apply_mitigation`) require explicit user confirmation.
- **RAG Knowledge Base**: SQLite vector store with pure Python cosine similarity indexing 5 operational runbooks.
- **Incident Postmortems**: Automated Markdown postmortems (Summary, Timeline, Impact, Root Cause, Mitigations) exportable as `.md`.
- **Propose & Simulate Mitigations**: Simulates candidate actions on isolated copies (`graph.clone()`), discards invalid proposals, and deterministically ranks by empirical metric deltas.

### 4. Evaluation Harness & LLMOps Panel (Review 2)
- **Offline Evaluation Runner** (`eval/evaluator.py`):
  - 50 programmatic templates (15 dev, 35 test) evaluated across 4 configurations over 3 runs (420 test queries):
    1. *Plain LLM* (receives full serialized topology as text in prompt, no tools, no RAG)
    2. *LLM + RAG* (runbooks only, no execution tools)
    3. *LLM + Tools* (custom engines, no RAG or grounding verifier)
    4. *Full NetPilot* (Tools + RAG + Number Grounding Verifier)
  - Scoring: 1% numeric tolerance, exact integer/set match, citation existence check, destructive gate verification.
  - Hallucination tracking: detects any ungrounded numbers across all 4 configurations.
  - Saves CSV, raw JSONL logs, Markdown summary, and Matplotlib comparison plots.
- **LLMOps Dashboard Panel**: Real-time token budget gauge (100k UTC limit), runbook knowledge base coverage, benchmark comparison table, and sanitized audit log.

---

## 🏗️ Repository Architecture

```
DAA_PROJ/
├── graph/                      # Directed graph data model & generators
│   ├── network.py              # Node, Edge, and Graph structures (from scratch)
│   └── generator.py            # Hierarchical CDN & benchmark generators
├── routing/                    # Algorithmic routing & flow engines (from scratch)
│   ├── bellman_ford.py         # Bellman-Ford SSSP with negative cycle detection
│   ├── floyd_warshall.py       # Floyd-Warshall APSP with path reconstruction
│   └── max_flow.py             # Edmonds-Karp (BFS), Ford-Fulkerson (DFS), Min-Cut
├── services/                   # Functional service layer
│   ├── network_service.py      # Session-scoped graph lifecycle management
│   ├── topology_service.py     # JSON/CSV validator & sample loader
│   ├── postmortem_service.py   # Incident postmortem generator
│   └── mitigation_service.py   # Mitigation simulation on isolated graph copies
├── storage/                    # Persistence layer
│   └── event_store.py          # SQLite event store (network_events.db)
├── rag/                        # Retrieval-Augmented Generation
│   ├── embedder.py             # DeterministicFakeEmbedder & OpenAI embedder
│   └── vector_store.py         # SQLite vector store with pure Python cosine similarity
├── runbooks/                   # Operational SOP runbooks
│   ├── link_failure_runbook.md
│   ├── congestion_runbook.md
│   ├── cache_miss_storm_runbook.md
│   ├── ddos_mitigation_runbook.md
│   └── bad_topology_upload_runbook.md
├── copilot/                    # NetPilot AI Copilot
│   ├── agent.py                # ReAct loop, delimiter isolation, confirmation gate
│   ├── tools.py                # Pydantic schemas & tool router
│   ├── verifier.py             # Number grounding & event citation validators
│   ├── guardrails.py           # Rate limiter (10 req/min) & token budget (100k UTC)
│   └── llm_provider.py         # OpenAI-compatible client & FakeLLMProvider
├── eval/                       # Evaluation & LLMOps Harness
│   ├── generator.py            # 50 programmatic questions (15 dev, 35 test)
│   ├── evaluator.py            # 4-configuration evaluation runner & plotting
│   └── results/                # CSV, JSON, Markdown, and Matplotlib plot outputs
├── benchmarks/                 # Empirical complexity benchmarking
│   └── benchmark.py            # Empirical runtime & operation counter runner
├── dashboard/                  # Interactive visual dashboard
│   ├── app.py                  # Flask web backend & REST API
│   ├── templates/index.html    # Single-page interface & modals
│   └── static/                 # Vis.js network visualization & CSS
├── tests/                      # Automated pytest test suite (66 tests)
├── Dockerfile                  # Production multi-stage Docker container
├── docker-compose.yml          # Containerized deployment
├── ARCHITECTURE.md             # Detailed system architecture document
├── PROGRESS.md                 # Milestone delivery audit log (M1 to M9)
└── ROADMAP.md                  # Evolution roadmap & future stretch goals
```

---

## 🚀 Quickstart & Setup

### 1. Local Environment Setup

```bash
# 1. Navigate to project root
cd DAA_PROJ

# 2. Create Python virtual environment
python3 -m venv .venv

# 3. Activate environment
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables (Optional)

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `LLM_API_KEY` | *(unset)* | OpenAI / OpenRouter API Key. If unset, NetPilot safely uses offline `FakeLLMProvider`. |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible endpoint. |
| `LLM_MODEL` | `gpt-4o-mini` | Model name. |
| `COPILOT_ENABLED` | `true` | Master kill switch for Copilot features. |
| `DAILY_TOKEN_BUDGET`| `100000` | Daily token spend cap (resets 00:00 UTC). |

---

## 💻 Running the Application

### 1. Launch Interactive Dashboard
```bash
python dashboard/app.py
```
Open **[http://localhost:5000](http://localhost:5000)** in your browser:
- **Shortest Path**: Trace lowest-latency routes using Bellman-Ford or Floyd-Warshall.
- **Max Flow**: Run Edmonds-Karp with super-sink allocation and visualize min-cut bottlenecks.
- **Fault Simulation**: Click "⚡ Kill Random Edge" to simulate outages and dynamic rerouting.
- **Postmortem Generator**: Click "📋 Generate Incident Postmortem" and download `.md` reports.
- **Mitigations Engine**: Click "💡 Mitigations" to evaluate topology upgrades on isolated graph copies.
- **LLMOps Panel**: Click "📈 LLMOps" to inspect token budgets, runbook health, and benchmark findings.
- **NetPilot Copilot**: Click "🤖 NetPilot Copilot" to converse with the autonomous network SRE.

### 2. Run Offline Evaluation Benchmark
```bash
# Run complete offline evaluation on test set (35 templates × 3 runs = 420 queries)
python -m eval.evaluator --dry-run --runs 3

# Test with a quick 3-question limit
python -m eval.evaluator --dry-run --limit 3 --runs 1

# Execute against a live LLM endpoint (requires LLM_API_KEY)
python -m eval.evaluator --real-run --runs 3
```

Results and comparison plots are saved directly to `eval/results/eval_comparison.png`.

### 3. Run Algorithmic Complexity Benchmarks
```bash
python benchmarks/benchmark.py
```
Generates empirical CSV data and Matplotlib asymptotic complexity plots in `benchmarks/results/`.

---

## 🧪 Automated Testing Suite

The test suite includes **66 automated pytest tests** covering:
- Graph data structures, mutations, dynamic link failures.
- Handcrafted 6-node ground truth routing verification.
- Cross-validation between Bellman-Ford, Floyd-Warshall, and NetworkX across 50 random topologies.
- Negative cycle detection.
- Edmonds-Karp and Ford-Fulkerson max flow cross-validation against NetworkX.
- JSON/CSV topology uploads with row-numbered error detection.
- Copilot ReAct agent loop, number grounding verifier, and destructive confirmation gate.
- RAG runbook chunking, cosine similarity, delimiter isolation, and event citation verification.
- Isolated mitigation simulations and deterministic metric ranking.
- Evaluation harness, scoring rules, hallucination tracking, and LLMOps endpoints.

To run the full suite:
```bash
pytest -v
```

All 66 tests execute in under 3 seconds with **100% pass rate**.

---

## 🐳 Docker Deployment

The project includes a multi-stage Dockerfile and `docker-compose.yml`:

```bash
# Build and run with Docker Compose
docker-compose up --build

# Run in background
docker-compose up -d

# Stop container
docker-compose down
```
Access the dashboard at **[http://localhost:5000](http://localhost:5000)**.

---

## 📊 Evaluation & LLMOps Findings

The offline evaluation harness evaluates 4 configurations across 420 test queries:

| Configuration | Description | Ground-Truth Accuracy | Hallucination Rate | p50 Latency |
| :--- | :--- | :---: | :---: | :---: |
| **Plain LLM** | Receives full topology text in prompt; no tools | 5.7% | **31.6%** | 85 ms |
| **LLM + RAG** | Access to runbooks only; no execution tools | 13.3% | 0.0% | 116 ms |
| **LLM + Tools** | Access to custom Python routing/flow engines | **61.9%** | **0.0%** | 90 ms |
| **Full NetPilot** | Tools + RAG + Number Grounding Verifier | **61.9%** | **0.0%** | 101 ms |

> [!NOTE]
> The table above reflects the verified synthetic baseline dry run generated by `eval/evaluator.py`. When run with a production LLM API key, live scores are automatically recorded with model metadata in `eval/results/eval_summary.json` and presented in the LLMOps modal.

---

## 📚 Documentation Links
- **[ARCHITECTURE.md](ARCHITECTURE.md)**: Detailed system architecture, data flow diagrams, SQLite schemas, RAG isolation, and guardrails.
- **[PROGRESS.md](PROGRESS.md)**: Chronological delivery audit log across all 9 milestones (M1 to M9).
- **[ROADMAP.md](ROADMAP.md)**: Review 1 and 2 completion status and future stretch goals (Live Mode traceroute, Karger's min-cut, Set Cover caching).
