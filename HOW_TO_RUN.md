# Mini CDN Routing Simulator & NetPilot: Complete Beginner's Guide

Welcome! This guide explains **what this project is**, **how to run it in 60 seconds**, and **walks you through every single button, feature, and function**—assuming zero prior background with CDNs or complex algorithms.

---

## 📖 1. What is this Project? (The Simple Explanation)

### What is a CDN?
Imagine you live in Tokyo and order a physical book from a publisher in New York. If it has to ship across the ocean every time, it takes days. Instead, what if the publisher keeps copies of popular books in local warehouses in Tokyo, London, Sydney, and Frankfurt? Now, your order arrives in 1 hour.

A **Content Delivery Network (CDN)** does exactly this for the internet (used by Cloudflare, Netflix, Akamai):
- **Origin Server**: The master server storing all original website files (videos, images, code).
- **Edge Servers (POPs)**: Satellite servers placed close to users around the world.
- **User Regions**: People browsing the web from different cities (e.g., Tokyo, London, Cape Town).
- **Links**: Fiber-optic communication cables connecting servers. Each link has:
  - **Latency (ms)**: Delay / travel time in milliseconds (lower is faster).
  - **Bandwidth Capacity (Mbps)**: Pipe thickness (how many megabits can travel at once).

### What does this Simulator do?
This software simulates an entire worldwide CDN network in your browser. It lets you:
1. **Find the fastest path** from any user to the best edge server.
2. **Simulate real-world disasters** (e.g., cutting a transatlantic cable) and watch traffic automatically reroute in real time.
3. **Calculate maximum network throughput** and pinpoint bottlenecks.
4. **Talk to an AI Copilot ("NetPilot")** that analyzes your network, tests "what-if" scenarios, writes incident postmortems, and suggests fixes.

---

## ⚡ 2. How to Run (Step-by-Step)

### Option A: Standard Run (Recommended)

Open your terminal, navigate to the folder, and run:

```bash
# 1. Enter the project folder
cd DAA_PROJ

# 2. Activate the virtual environment
source .venv/bin/activate

# 3. Start the dashboard web server
python dashboard/app.py
```

Now open your web browser and go to:
👉 **[http://localhost:5000](http://localhost:5000)**

*(Press `Ctrl + C` in the terminal when you want to stop the server).*

---

### 🔑 Enabling the NetPilot AI Copilot with Groq (Fast & Free)

The project includes an automatic integration with **Groq** ([https://console.groq.com/keys](https://console.groq.com/keys)). To activate live AI copilot features:

```bash
# Set your Groq API key (starts with gsk_...)
export GROQ_API_KEY="gsk_your_groq_api_key_here"

# Start the server (Groq endpoint and llama-3.3-70b-versatile are auto-detected!)
python dashboard/app.py
```

*Note: If `GROQ_API_KEY` is not set, the simulator and Copilot automatically and safely fall back to the built-in offline `FakeLLMProvider`.*

---

### Option B: Run via Docker (Zero Configuration)

If you have Docker installed:

```bash
cd DAA_PROJ
docker-compose up --build
```
Then open **[http://localhost:5000](http://localhost:5000)**.

---

### Option C: Run Tests and Offline Benchmarks

```bash
cd DAA_PROJ
source .venv/bin/activate

# Run all 66 automated tests (takes ~2 seconds)
pytest -v

# Run the 4-Configuration AI Evaluation Benchmark
python -m eval.evaluator --dry-run --runs 1 --limit 3

# Run the theoretical algorithmic complexity benchmarks
python benchmarks/benchmark.py
```

---

## 🖥️ 3. Interactive Dashboard Tour: Feature by Feature

When you open **[http://localhost:5000](http://localhost:5000)**, you will see a dark-mode control room:

```
+-----------------------------------------------------------------------------------+
| Mini CDN Routing & Flow Simulator         [📁 Topology] [📊 Benchmark] [💡 Mitigations] [📈 LLMOps] [🤖 Copilot] |
+-----------------------------------------------------------------------------------+
| [CONTROL SIDEBAR]              | [VIS.JS INTERACTIVE NETWORK CANVAS]              |
| Mode: [Shortest Path] [MaxFlow] |                                                   |
| 1. Algorithm Selection         |   (Origin: North America)                         |
| 2. User Source Selection       |          │                                        |
| 3. [Compute Shortest Path]     |   (Edge: Frankfurt) ──── (Edge: Tokyo)            |
| 4. Fault Simulation & Outages  |          │                     │                  |
| 5. Telemetry & Metrics Output  |   (User: London)         (User: Japan)            |
+-----------------------------------------------------------------------------------+
```

---

### Feature 1: The Interactive Network Canvas
- **What you see**:
  - 🟡 **Orange Star Node**: The central **Origin Server**.
  - 🔵 **Blue Square Nodes**: **Edge Servers** distributed globally (e.g., Tokyo, Frankfurt, London, Sydney).
  - 🟢 **Green Circle Nodes**: **User Regions** (e.g., User 1, User 2, User 3).
  - **Lines (Edges)**: Directed links. Numbers on hover display latency (e.g. `24.5 ms`) and capacity (e.g. `1000 Mbps`).
- **How to interact**:
  - **Click and drag** any node to rearrange.
  - **Scroll wheel** to zoom in and out.
  - **Click "Fit View"** at the top right of the canvas to auto-center the network.

---

### Feature 2: Shortest-Path Routing
*Goal: Find the fastest route from a user's location to the nearest edge server.*

1. Look at the left sidebar under **1. Routing Algorithm**:
   - Choose **Bellman-Ford** ($O(V \cdot E)$) or **Floyd-Warshall** ($O(V^3)$).
2. Under **2. User Region**, pick a user (e.g., `user_1 · North America East`).
3. Click the blue **"Compute Shortest Path"** button.
4. **What happens**:
   - The fastest multi-hop path illuminates in bright cyan/blue on the graph.
   - The sidebar displays:
     - **Best Edge Server**: E.g., `edge_1 · New York POP`.
     - **Total Latency**: E.g., `12.40 ms`.
     - **Hop Count**: Number of intermediate hops (e.g., `2 hops`).
     - **Compute Time**: Milliseconds taken by Python to calculate the route.
     - **Elementary Operations**: Exact count of edge relaxation comparisons made.
5. Click **"Compare Both"**:
   - Runs both Bellman-Ford and Floyd-Warshall simultaneously.
   - Proves that both algorithms arrive at the exact same optimal distance, while displaying a side-by-side comparison of execution time and operation counts.

---

### Feature 3: Dynamic Fault Simulation (Network Disasters)
*Goal: Simulate broken undersea cables and watch traffic self-heal.*

1. In the sidebar under **Fault Simulation & Dynamic Rerouting**:
2. Click **"⚡ Kill Random Edge"**:
   - A random active link in the network is severed.
   - The event log displays the failure: `Severed link: user_1 <-> edge_1`.
   - The path instantly recalculates and visually reroutes around the broken link.
   - Notice the latency increases (e.g., from `12.4 ms` to `28.6 ms`) and hop count increases to find a detour.
3. Click **"Reset Network"** to restore all links back to healthy.

---

### Feature 4: What-If Link Failure Analysis
*Goal: Test "What if cable X breaks?" safely without touching the live network.*

1. In the sidebar under **"What-If Analysis (Non-Destructive)"**:
2. Select an edge from the dropdown (or type `user_1<->edge_1`).
3. Click **"Simulate Impact"**.
4. **What happens**:
   - The engine clones the graph in memory, cuts the link on the clone, and compares baseline vs post-failure routes.
   - Displays:
     - Baseline Latency: `14.2 ms`
     - Post-Failure Latency: `32.0 ms`
     - Delta: `+17.8 ms (125% increase)`
   - The live network is **100% untouched**.

---

### Feature 5: Max Flow & Min-Cut Bottleneck Analysis
*Goal: Find how much total bandwidth can flow at once and where the bottleneck is.*

1. At the very top of the sidebar, switch the tab from **"Shortest Path"** to **"Max Flow & Min-Cut"**.
2. Select algorithm: **Edmonds-Karp (BFS)** or **Ford-Fulkerson (DFS)**.
3. Click **"Compute Max Flow"**.
4. **What happens**:
   - Traverses the network from the Origin to all Edge servers using a virtual **Super-Sink**.
   - **Max Flow**: Displays total delivered throughput (e.g., `2500.0 Mbps`).
   - **Augmenting Paths**: Number of distinct paths discovered.
   - **Min-Cut Bottleneck Edges**: Highlights the exact cut of critical links in bright red that choke total throughput.
   - **Bottleneck Capacity**: Sum of bandwidth across the bottleneck links.

---

### Feature 6: Topology Manager (Custom Network Uploads)
*Goal: Load custom network designs or enterprise samples.*

1. In the top navigation bar, click **"📁 Load Topology"**.
2. A modal window opens:
   - Click **"Load Campus Network"** (15 nodes) or **"Load Cloud Multi-Region"** (12 nodes).
   - Or download the starter JSON / CSV template, edit your own links, and upload your custom topology.
   - The validator checks for duplicate nodes, negative capacities, and missing origins, returning exact line numbers if you made a typo.

---

### Feature 7: Automated Incident Postmortem Generator
*Goal: Generate a formal SRE postmortem report after an outage.*

1. Cause an outage by clicking **"⚡ Kill Random Edge"**.
2. A green button appears in the fault panel: **"📋 Generate Incident Postmortem"**.
3. Click it. A modal pops up with a complete structured Markdown report:
   - **1. Summary**: Incident ID, timestamp, severed link.
   - **2. Chronological Timeline**: Table of exact events and durations.
   - **3. Impact Assessment**: Before-and-after latency and hop progression.
   - **4. Root Cause Analysis**: Mechanistic breakdown of the link severance.
   - **5. Preventative Mitigations**: SRE recommendations.
4. Click **"⬇️ Download .md"** to save the report directly to your computer.

---

### Feature 8: Propose & Simulate Mitigations Engine
*Goal: Ask the system to evaluate network upgrades and rank them by measured impact.*

1. In the top navigation bar, click **"💡 Mitigations"**.
2. Select your optimization goal:
   - *Maximize Network Throughput*
   - *Minimize User Latency*
   - *Resolve Min-Cut Bottlenecks*
3. Click **"Simulate Candidates"**:
   - The simulator creates isolated cloned graph copies, applies candidate actions (adding redundant links, upgrading bottleneck capacities), and measures the empirical delta in latency and throughput.
   - Discards invalid candidates and deterministically ranks valid ones.
4. Review the table: Rank, Action, Target, Proposed Value, Rationale, and Measured Impact.
5. Click **"Apply"**:
   - Prompts you with an explicit confirmation dialog before modifying the live network.

---

### Feature 9: NetPilot AI Copilot (Slide-out Assistant)
*Goal: Chat with an AI assistant that actually runs code instead of hallucinating.*

1. In the top navigation bar, click the purple **"🤖 NetPilot Copilot"** button.
2. A slide-out chat drawer opens from the right side.
3. Click any of the quick-action chips or type a message:
   - *"What is the optimal route for user_1?"*
   - *"What happens if user_1<->edge_1 fails?"*
   - *"What is the maximum flow from origin?"*
   - *"Where is the bottleneck?"*
   - *"What is the runbook procedure for link failure?"*
4. **Notice the Green Shield Badge**:
   - Every answer displays: `🛡️ Grounded in tool telemetry · All numbers verified`.
   - The AI **never guesses numbers**; it executes the Python tools and reports verified facts.

---

### Feature 10: LLMOps & Evaluation Benchmark Panel
*Goal: Enterprise observability for AI agent accuracy, token spend, and safety.*

1. In the top navigation bar, click **"📈 LLMOps"**.
2. A comprehensive dashboard modal opens:
   - **Daily Token Budget (UTC)**: Gauge showing tokens used today against the 100,000 token limit.
   - **Runbooks & Knowledge Base**: Health status and total indexed vector chunks.
   - **Configuration Benchmark Comparison**: Table comparing all 4 architectural configurations:
     - *Plain LLM* (mental arithmetic): High hallucination (31.6%), low accuracy.
     - *LLM + RAG* (docs only): Good for procedures, cannot compute math.
     - *LLM + Tools* (engine execution): 0% hallucination, high accuracy.
     - *Full NetPilot* (Tools + RAG + Verifier): 0% hallucination, verified numbers.
   - **Embedded Plot**: Visual graphs showing accuracy, hallucination, latency, and cost.
   - **Recent Audit Log**: Table of the last 10 tool calls with HTML-escaped parameters and redacted credentials.

---

## 🔍 4. Behind the Scenes: Which Python File Does What?

If you want to look at the code, here is where each algorithm lives:

| Component | File Path | What it Does |
| :--- | :--- | :--- |
| **Graph Model** | [graph/network.py](graph/network.py) | Custom Node, Edge, and Graph classes. Deep copy (`clone()`), edge removal, weight updates. |
| **Bellman-Ford SSSP** | [routing/bellman_ford.py](routing/bellman_ford.py) | Single-source shortest path, edge relaxations over $|V|-1$ passes, negative cycle detection, operation counter ($O(V \cdot E)$). |
| **Floyd-Warshall APSP**| [routing/floyd_warshall.py](routing/floyd_warshall.py)| All-pairs shortest path dynamic programming matrix, predecessor reconstruction, operation counter ($O(V^3)$). |
| **Max Flow Engine** | [routing/max_flow.py](routing/max_flow.py) | Edmonds-Karp (BFS) and Ford-Fulkerson (DFS), residual graph $G_f$, super-sink, and min-cut reachability partition ($O(V \cdot E^2)$). |
| **Network Service** | [services/network_service.py](services/network_service.py)| Manages active sessions, runs routing/flow queries, coordinates failure injections. |
| **Mitigations Engine**| [services/mitigation_service.py](services/mitigation_service.py)| Clones graphs, simulates candidate changes, ranks by empirical deltas, confirmation gates. |
| **Postmortem Service**| [services/postmortem_service.py](services/postmortem_service.py)| Queries SQLite event store and drafts Markdown postmortem reports. |
| **Event Store** | [storage/event_store.py](storage/event_store.py)| SQLite database (`network_events.db`) logging immutable audit trails of all network events. |
| **Vector Store & RAG**| [rag/vector_store.py](rag/vector_store.py)| Pure Python cosine similarity search over chunked markdown runbooks in `runbooks/`. |
| **Copilot ReAct Agent**| [copilot/agent.py](copilot/agent.py)| 5-step ReAct loop, delimiter security isolation, destructive confirmation gate. |
| **Grounding Verifier**| [copilot/verifier.py](copilot/verifier.py)| Anti-hallucination regex engine ensuring every number in answers matches tool telemetry. |
| **Guardrails** | [copilot/guardrails.py](copilot/guardrails.py)| 10 req/min sliding-window rate limiter, 100k daily token budget, master kill switch. |
| **Evaluation Harness**| [eval/evaluator.py](eval/evaluator.py)| Runs 420 test queries across 4 configs, calculates accuracy/hallucination, generates plots. |
| **Web Dashboard** | [dashboard/app.py](dashboard/app.py)| Flask REST API serving endpoints, network visualization, and security sanitization. |

---

## ❓ 5. Frequently Asked Questions (FAQ)

### Q: Do I need an OpenAI API key to use this?
**A:** No! The system includes a built-in deterministic `FakeLLMProvider`. If `LLM_API_KEY` is not set, the Copilot and Evaluation harness run completely offline with 100% functionality.

### Q: Are any external routing libraries used?
**A:** No. Bellman-Ford, Floyd-Warshall, Edmonds-Karp, Ford-Fulkerson, and Min-Cut are written 100% from scratch in pure Python. NetworkX is used only in test files (`tests/test_cross_validation.py`) to verify our scratch algorithms against an established baseline.

### Q: What happens if a link is severed and a user becomes disconnected?
**A:** The routing engine detects that distance is infinite (`float('inf')`), displays an alert indicating no reachable edge server exists, and logs the disconnection event to the event store.

### Q: How do I know the AI isn't making up numbers?
**A:** Click the purple Copilot button and ask a question. The response includes a green shield badge `🛡️ Grounded in tool telemetry`. The built-in number verifier parses every number in the LLM's response and compares it against the raw numerical output of the Python engine. If a number does not match, the response is flagged.

---

Enjoy exploring the **Mini CDN Routing Simulator & NetPilot**! For deep architectural details, see [ARCHITECTURE.md](ARCHITECTURE.md).
