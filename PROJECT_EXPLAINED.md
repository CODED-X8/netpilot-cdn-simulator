# Mini CDN Routing Simulator & NetPilot: Complete Project & Codebase Guide

Welcome to the definitive architectural, operational, and code-level guide for the **Mini CDN Routing Simulator** and the **NetPilot AI Copilot**.

This document is designed to give you a 100% complete understanding of:
1. **What this project is and what problem it solves.**
2. **How every subsystem and component works.**
3. **The file and folder hierarchy.**
4. **Every single class, function, parameter, and return value across the entire codebase.**
5. **How the underlying algorithms work mathematically.**
6. **How to run, test, and interact with the application.**

---

## Table of Contents

- [1. High-Level Overview: What is this Project?](#1-high-level-overview-what-is-this-project)
  - [The Real-World Analogy (What is a CDN?)](#the-real-world-analogy-what-is-a-cdn)
  - [The DAA Core Philosophy: Zero Routing Libraries](#the-daa-core-philosophy-zero-routing-libraries)
  - [The NetPilot Copilot Rule](#the-netpilot-copilot-rule)
- [2. System Architecture & Request Lifecycle](#2-system-architecture--request-lifecycle)
  - [Architecture Flow Diagram](#architecture-flow-diagram)
  - [The Multi-Session Isolation Model](#the-multi-session-isolation-model)
- [3. Repository Directory Structure](#3-repository-directory-structure)
- [4. Deep Dive: Graph Data Model (`graph/`)](#4-deep-dive-graph-data-model-graph)
  - [`graph/network.py`](#graphnetworkpy)
  - [`graph/generator.py`](#graphgeneratorpy)
- [5. Deep Dive: Core Routing & Max Flow Engines (`routing/`)](#5-deep-dive-core-routing--max-flow-engines-routing)
  - [`routing/bellman_ford.py`](#routingbellman_fordpy)
  - [`routing/floyd_warshall.py`](#routingfloyd_warshallpy)
  - [`routing/max_flow.py`](#routingmax_flowpy)
- [6. Deep Dive: Business Logic & Services (`services/`)](#6-deep-dive-business-logic--services-services)
  - [`services/network_service.py`](#servicesnetwork_servicepy)
  - [`services/topology_service.py`](#servicestopology_servicepy)
  - [`services/postmortem_service.py`](#servicespostmortem_servicepy)
  - [`services/mitigation_service.py`](#servicesmitigation_servicepy)
- [7. Deep Dive: Event Store & Persistence (`storage/`)](#7-deep-dive-event-store--persistence-storage)
  - [`storage/event_store.py`](#storageevent_storepy)
- [8. Deep Dive: RAG Knowledge Base & Semantic Search (`rag/`)](#8-deep-dive-rag-knowledge-base--semantic-search-rag)
  - [`rag/embedder.py`](#ragembedderpy)
  - [`rag/vector_store.py`](#ragvector_storepy)
- [9. Deep Dive: NetPilot AI Copilot (`copilot/`)](#9-deep-dive-netpilot-ai-copilot-copilot)
  - [`copilot/llm_provider.py`](#copilotllm_providerpy)
  - [`copilot/guardrails.py`](#copilotguardrailspy)
  - [`copilot/verifier.py`](#copilotverifierpy)
  - [`copilot/tools.py`](#copilottoolspy)
  - [`copilot/agent.py`](#copilotagentpy)
- [10. Deep Dive: Web Application Backend (`dashboard/`)](#10-deep-dive-web-application-backend-dashboard)
  - [`dashboard/app.py`](#dashboardapppy)
  - [Frontend Architecture (`static/` & `templates/`)](#frontend-architecture-static--templates)
- [11. Deep Dive: Offline Evaluation Benchmark (`eval/`)](#11-deep-dive-offline-evaluation-benchmark-eval)
  - [`eval/generator.py`](#evalgeneratorpy)
  - [`eval/evaluator.py`](#evalevaluatorpy)
- [12. Comprehensive Master Function Directory](#12-comprehensive-master-function-directory)
- [13. How to Run, Test & Debug](#13-how-to-run-test--debug)

---

## 1. High-Level Overview: What is this Project?

### The Real-World Analogy (What is a CDN?)
When you watch a Netflix show or load an image on Instagram, your computer does not fetch that video or image from a single master data center in California. If millions of people in Tokyo, London, Sydney, and Mumbai did that simultaneously, the transatlantic fiber cables would choke from bandwidth congestion, and latency (the round-trip travel time) would make streaming unwatchable.

To solve this, companies deploy a **Content Delivery Network (CDN)**:
- **Origin Server**: The master server storing the canonical database and website assets.
- **Edge Servers (Points of Presence / POPs)**: Caching servers placed in cities worldwide (e.g., Frankfurt, Tokyo, São Paulo).
- **User Regions**: Geographic client populations (e.g., North America, East Asia, South Asia).
- **Communication Links (Edges)**: Directed fiber connections with two critical physical constraints:
  1. **Latency (ms)**: The delay for a packet to traverse the link. Lower is better.
  2. **Bandwidth Capacity (Mbps)**: The maximum data rate that can travel through the pipe at one time.

### The DAA Core Philosophy: Zero Routing Libraries
This project is built for a University **Design and Analysis of Algorithms (DAA)** course. A foundational constraint across the entire project is:
> **No external graph or network routing libraries (such as NetworkX, igraph, or SciPy) are permitted in the application code.**

Every data structure, graph representation, shortest path algorithm, augmenting path search, residual graph, and min-cut solver is written **completely from scratch in pure Python**. NetworkX is installed exclusively inside the automated test suite as an independent benchmark to verify our algorithms.

### The NetPilot Copilot Rule
In addition to the algorithmic engine, the project features **NetPilot**, an AI Network Reliability Copilot. A strict rule governs NetPilot:
> **The Large Language Model (LLM) NEVER computes routes, flows, capacities, or numbers.**

LLMs are probabilistic token predictors and are notoriously bad at graph traversal and arithmetic. If an LLM tries to guess the shortest path or max throughput, it hallucinates. Therefore, NetPilot acts strictly as an **agentic coordinator**:
1. When a user asks a question, NetPilot decides which deterministic Python tool to call.
2. Our scratch Python engine runs the algorithm and returns exact numbers.
3. NetPilot formats and explains the tool's result in plain English.
4. An automated **Number Grounding Verifier** checks the LLM's response. If the LLM mentions a single number that was not returned by the tool, it flags the response with a visible warning.

---

## 2. System Architecture & Request Lifecycle

### Architecture Flow Diagram

```
                                      +------------------------------------+
                                      |     User Browser / Vis.js UI       |
                                      +-----------------+------------------+
                                                        |
                                          HTTP REST / JSON Requests
                                                        v
                                      +------------------------------------+
                                      |       Flask Backend (app.py)       |
                                      +--------+------------------+--------+
                                               |                  |
                       +-----------------------+                  +-----------------------+
                       |                                                                  |
                       v                                                                  v
+---------------------------------------------+                +--------------------------------------------------+
|      Business Services (services/)          |                |         NetPilot Copilot (copilot/)              |
|  - network_service (Routing & Faults)       |                |  - guardrails.py (Rate Limit & Token Budget)     |
|  - topology_service (JSON/CSV Validation)   |                |  - agent.py (Tool-calling ReAct Loop)            |
|  - postmortem_service (Incident Reports)    |                |  - tools.py (Pydantic Schemas & Tool Router)     |
|  - mitigation_service (What-if & Reroute)   |                |  - verifier.py (Anti-Hallucination Grounding)    |
+----------------------+----------------------+                +--------------------------+-----------------------+
                       |                                                                  |
                       v                                                                  v
+---------------------------------------------+                +--------------------------------------------------+
|    Core Algorithmic Engines (routing/)      |                |       RAG & Incident Retrieval (rag/)            |
|  - Bellman-Ford SSSP (O(|V|*|E|))           |                |  - vector_store.py (SQLite Document Embeddings)  |
|  - Floyd-Warshall APSP (O(|V|^3))           |                |  - embedder.py (Deterministic Keyword Hasher)    |
|  - Edmonds-Karp & Ford-Fulkerson Max Flow   |                |  - 5 Operational Incident Runbooks               |
|  - Min-Cut & Bottleneck Analysis            |                +--------------------------+-----------------------+
+----------------------+----------------------+                                           |
                       |                                                                  |
                       +-------------------------------+----------------------------------+
                                                       |
                                                       v
                                      +------------------------------------+
                                      |  SQLite Event Store (network_events.db)
                                      |   Logs every route, fault, failure |
                                      +------------------------------------+
```

### The Multi-Session Isolation Model
The application supports multi-tenant isolation via the `X-Session-ID` HTTP header:
- Each user or browser tab gets its own isolated in-memory network graph (`_ACTIVE_TOPOLOGIES[session_id]`).
- Cutting a link or uploading a custom topology in one session does not affect another user's topology.
- Sessions automatically clean up after inactivity (2-hour TTL).

---

## 3. Repository Directory Structure

```
DAA_PROJ/
├── benchmarks/              # Algorithmic complexity benchmarks and empirical plotting
│   ├── benchmark.py         # Runs runtime vs. |V| and |E| scaling tests
│   └── results/             # Saved benchmark figures (complexity_benchmark.png)
├── copilot/                 # NetPilot AI Copilot implementation
│   ├── __init__.py
│   ├── agent.py             # Multi-step tool-calling agent loop
│   ├── guardrails.py        # Rate limiting, token budget tracking, kill switch
│   ├── llm_provider.py      # Groq / OpenAI API client & offline fake provider
│   ├── tools.py             # Pydantic schemas, OpenAPI tool specs, tool dispatcher
│   └── verifier.py          # Numeric & event-ID anti-hallucination verifiers
├── dashboard/               # Web application presentation layer
│   ├── app.py               # Flask REST API backend and routes
│   ├── templates/
│   │   └── index.html       # Single-page dashboard UI (HTML5 + Tailwind-style CSS)
│   └── static/
│       ├── css/style.css    # Custom dark/light mode styles & layout rules
│       └── js/main.js       # Frontend controller & Vis.js network canvas engine
├── eval/                    # Offline evaluation benchmark harness (Milestone M8)
│   ├── evaluator.py         # 4-configuration runner (Plain vs RAG vs Tools vs Full)
│   ├── generator.py         # Generates 50 question templates with ground-truth
│   └── results/             # Benchmark outputs (eval_results.csv, eval_summary.md)
├── graph/                   # Graph data structures and topology generators
│   ├── __init__.py
│   ├── generator.py         # Generates realistic hierarchical CDNs and random graphs
│   └── network.py           # Core Node, Edge, and Graph classes
├── rag/                     # Retrieval-Augmented Generation subsystem
│   ├── __init__.py
│   ├── embedder.py          # Deterministic keyword vector embedder & API embedder
│   └── vector_store.py      # SQLite vector database with pure Python cosine similarity
├── routing/                 # Pure Python scratch algorithms (Zero external libraries)
│   ├── __init__.py
│   ├── bellman_ford.py      # Bellman-Ford SSSP with negative cycle detection
│   ├── floyd_warshall.py    # Floyd-Warshall APSP with path reconstruction
│   └── max_flow.py          # Edmonds-Karp, Ford-Fulkerson, Min-Cut & Bottleneck finder
├── runbooks/                # Markdown runbooks for network incident triage
│   ├── bad_topology_upload_runbook.md
│   ├── congestion_runbook.md
│   ├── latency_regression_runbook.md
│   ├── link_failure_runbook.md
│   └── regional_outage_runbook.md
├── samples/                 # Sample custom topologies for upload testing
│   ├── sample_topology.json
│   ├── sample_nodes.csv
│   └── sample_edges.csv
├── services/                # Business logic layer isolating Flask from raw engines
│   ├── __init__.py
│   ├── mitigation_service.py # Propose, simulate, and verify candidate network fixes
│   ├── network_service.py    # Routing, fault injection, and state coordinator
│   ├── postmortem_service.py # Structured incident postmortem Markdown generator
│   └── topology_service.py   # JSON/CSV schema validator with row-numbered errors
├── storage/                 # Persistence layer
│   ├── __init__.py
│   └── event_store.py       # SQLite database logging all network events
├── tests/                   # Automated pytest suite (67 tests, 100% pass)
│   ├── test_copilot.py
│   ├── test_cross_validation.py
│   ├── test_deployment_and_limits.py
│   ├── test_eval.py
│   ├── test_graph.py
│   ├── test_handcrafted.py
│   ├── test_max_flow.py
│   ├── test_mitigations.py
│   ├── test_negative_cycle.py
│   ├── test_postmortem.py
│   ├── test_rag.py
│   ├── test_service_and_storage.py
│   └── test_topology.py
├── .env.example             # Example environment variable file
├── ARCHITECTURE.md          # System architecture design documentation
├── HOW_TO_RUN.md            # Quickstart guide for non-technical users
├── PROGRESS.md              # Milestone audit log (M1 through M9)
├── README.md                # Project README
└── ROADMAP.md               # Future stretch goals
```

---

## 4. Deep Dive: Graph Data Model (`graph/`)

The `graph/` package defines how vertices, edges, and networks are modeled and instantiated.

### `graph/network.py`

#### 1. `Node`
Represents an individual physical or logical vertex in the network.
- **Attributes**:
  - `id: str`: Unique identifier (e.g. `origin_1`, `edge_3`, `user_2`).
  - `node_type: str`: One of `{"origin", "edge_server", "user_region", "transit"}`.
  - `label: str`: Human-readable display label (e.g. `Edge 3 · Frankfurt`).
  - `metadata: Dict[str, Any]`: Optional attributes such as `city`, `tier`, `cache_capacity_gb`, `client_density`.
- **Methods**:
  - `to_dict() -> Dict[str, Any]`: Serializes the node into a JSON-compatible dictionary.
  - `__eq__`, `__hash__`: Hashable by `id` so nodes can be stored in sets or used as dict keys.

#### 2. `Edge`
Represents a directed communication link between two nodes.
- **Attributes**:
  - `u: str`: Source node ID.
  - `v: str`: Destination node ID.
  - `latency: float`: Edge weight representing delay in milliseconds.
  - `bandwidth_capacity: float`: Pipe capacity in Megabits per second (Mbps). Defaults to `1000.0`.
  - `metadata: Dict[str, Any]`: Optional metadata (e.g. cable name, link status).
- **Methods**:
  - `to_dict() -> Dict[str, Any]`: Serializes edge to a dictionary.

#### 3. `Graph`
Directed, weighted adjacency-list graph implementation.
- **Internal Storage**:
  - `self.nodes: Dict[str, Node]`: Map from `node_id` to `Node` object.
  - `self.adj: Dict[str, Dict[str, Edge]]`: Nested adjacency map. `self.adj[u][v]` holds the `Edge(u, v)`.
- **Methods**:
  - `add_node(node_id: str, node_type: str = "edge_server", label: Optional[str] = None, **metadata) -> Node`: Adds a node if it does not already exist.
  - `has_node(node_id: str) -> bool`: Checks existence in O(1) time.
  - `get_node(node_id: str) -> Optional[Node]`: Retrieves a node or `None`.
  - `add_edge(u: str, v: str, latency: float, bandwidth_capacity: float = 1000.0, bidirectional: bool = False, **metadata) -> Edge`: Inserts directed edge u -> v. If `bidirectional=True`, also inserts v -> u. Automatically creates u or v if they do not yet exist.
  - `remove_edge(u: str, v: str, bidirectional: bool = False) -> bool`: Deletes directed edge u -> v. Used by fault simulation to model cut cables. Returns `True` if found and deleted.
  - `has_edge(u: str, v: str) -> bool`: Checks if edge u -> v exists in O(1).
  - `get_edge(u: str, v: str) -> Optional[Edge]`: Retrieves `Edge` object or `None`.
  - `update_edge_weight(u: str, v: str, latency: float, bandwidth_capacity: Optional[float] = None, bidirectional: bool = False) -> bool`: Updates latency/bandwidth on an existing edge to model congestion.
  - `get_adjacency() -> Dict[str, Dict[str, float]]`: Returns a simplified nested dictionary `{u: {v: latency}}`.
  - `get_nodes() -> List[Node]`: Returns a list of all nodes.
  - `get_edges() -> List[Edge]`: Flattens and returns all directed edges in the network.
  - `get_nodes_by_type(node_type: str) -> List[Node]`: Filters nodes by their type tag.
  - `clone() -> Graph` / `copy() -> Graph`: Performs a deep copy (`copy.deepcopy(self)`). Crucial for "what-if" counterfactual simulations without corrupting the live topology.
  - `to_dict() -> Dict[str, Any]`: Full JSON serialization `{"nodes": [...], "edges": [...]}`.
  - `edge_count() -> int` and `__len__()`: Returns total edges and total nodes.

---

### `graph/generator.py`

#### 1. `generate_cdn_topology(...) -> Graph`
Generates a realistic, production-style hierarchical CDN network:
- **Structure**:
  - **1 Origin**: `origin_1` ("Central DC").
  - **8 Edge POPs**: Interconnected backbone mesh spanning global cities (Virginia, Oregon, Frankfurt, Stockholm, Tokyo, Singapore, São Paulo, Cape Town).
  - **5 User Regions**: `user_1` through `user_5`.
  - **6 Regional Transit Relays**: `transit_apac_1`, `transit_latam_2`, etc.
- **Multi-Hop Guarantee**: To demonstrate genuine routing algorithms (rather than trivial 1-hop lookups), `user_3`, `user_4`, and `user_5` route exclusively through ISP transit relays, guaranteeing a 3+ hop path to their nearest edge server.
- **Parameters**: `num_origins`, `num_edges`, `num_users`, `min_latency`, `max_latency`, `seed`.

#### 2. `generate_random_connected_graph(...) -> Graph`
Constructs a random connected graph for stress testing, property-based testing, and complexity benchmarking.
- **Process**: First builds a random spanning tree to guarantee overall connectivity, then injects additional random edges until the target density or edge count is reached.

---

## 5. Deep Dive: Core Routing & Max Flow Engines (`routing/`)

Every algorithm in this package is implemented from first principles.

### `routing/bellman_ford.py`

#### Algorithmic Concept: Single-Source Shortest Path (SSSP)
Bellman-Ford solves the shortest path problem from a single starting vertex to all other vertices.
- **Time Complexity**: O(|V| * |E|), where |V| is the number of vertices and |E| is the number of directed edges.
- **Space Complexity**: O(|V|) for distance and predecessor tables.
- **Advantage over Dijkstra**: Bellman-Ford can handle edges with negative weights and detect negative-weight cycles.

#### Mathematical Steps:
1. Initialize `dist[source] = 0` and `dist[v] = inf` for all v != source.
2. **Relaxation**: Iterate |V| - 1 times. In each iteration, examine every directed edge (u, v) with weight w:
   if dist[u] + w < dist[v] => dist[v] = dist[u] + w, pred[v] = u
3. **Negative Cycle Check**: Run an extra |V|-th iteration across all edges. If any edge can still be relaxed, a negative-weight cycle exists that is reachable from the source.

#### Classes & Functions:
- **`NegativeCycleException(Exception)`**: Custom exception raised when a negative cycle is detected.
- **`BellmanFordResult`**:
  - `source: str`: Source node ID.
  - `distances: Dict[str, float]`: Shortest distance from source to each node.
  - `predecessors: Dict[str, Optional[str]]`: Predecessor map for path reconstruction.
  - `operations: int`: Exact count of relaxation comparisons executed (used in complexity benchmarks).
  - `has_negative_cycle: bool`: Flag indicating if a cycle was found.
  - `get_path(target: str) -> Optional[List[str]]`: Backtracks through `predecessors` from `target` to `source` and reverses the list to return `[source, ..., target]`. Detects loops to avoid infinite cycling.
- **`bellman_ford(graph: Graph, source: str, detect_negative_cycle: bool = True, early_stopping: bool = False) -> BellmanFordResult`**:
  Executes the algorithm on `graph`.
- **`find_best_edge_server_bf(graph: Graph, user_region_id: str, early_stopping: bool = False) -> Dict[str, Any]`**:
  Runs `bellman_ford` starting from `user_region_id`, scans all nodes of type `"edge_server"`, identifies the one with the minimum latency, reconstructs the path, and returns the result.

---

### `routing/floyd_warshall.py`

#### Algorithmic Concept: All-Pairs Shortest Path (APSP)
Floyd-Warshall is a dynamic programming algorithm that computes the shortest path between every pair of vertices in the graph simultaneously.
- **Time Complexity**: O(|V|^3) via 3 nested loops.
- **Space Complexity**: O(|V|^2) to store the distance matrix and the path reconstruction matrix.

#### Mathematical Steps:
1. Build a |V| x |V| matrix D where D[i][j] = weight(i, j) if edge exists, 0 if i=j, and inf otherwise.
2. Intermediate Vertex Relaxation: For k = 1 ... |V|, allow vertex k to act as an intermediate hop:
   D[i][j] = min(D[i][j], D[i][k] + D[k][j])
3. If D[i][i] < 0 for any vertex i, the graph contains a negative cycle.

#### Classes & Functions:
- **`FloydWarshallResult`**:
  - `nodes: List[str]`: Ordered list of vertex IDs corresponding to matrix indices.
  - `dist: List[List[float]]`: 2D matrix of shortest distances.
  - `next_node: List[List[Optional[int]]]`: Next-hop matrix for path reconstruction.
  - `operations: int`: Number of inner-loop comparison steps performed (|V|^3).
  - `get_distance(u: str, v: str) -> float`: Returns distance between u and v in O(1).
  - `get_path(u: str, v: str) -> Optional[List[str]]`: Reconstructs the complete vertex sequence [u, ..., v] using `next_node`.
  - `get_distance_dict(source: str) -> Dict[str, float]`: Converts row `source` into a standard dictionary.
  - `to_matrix_dict() -> Dict[str, Any]`: Formats the entire matrix as a nested dict for frontend visualization.
- **`floyd_warshall(graph: Graph, detect_negative_cycle: bool = True) -> FloydWarshallResult`**:
  Computes APSP across the graph.
- **`find_best_edge_server_fw(graph: Graph, user_region_id: str) -> Dict[str, Any]`**:
  Computes APSP, inspects distances from `user_region_id` to all edge servers, and returns the lowest-latency edge server and path.

---

### `routing/max_flow.py`

#### Algorithmic Concept: Maximum Flow & The Max-Flow Min-Cut Theorem
Calculates the maximum amount of traffic (bandwidth in Mbps) that can flow from a source (Origin) to one or more sinks (Edge servers or User populations) without exceeding the bandwidth capacity of any communication link.

1. **Virtual Super-Sink**:
   When multiple destination sinks exist (e.g., traffic heading to 8 edge servers), the engine creates a virtual node `__super_sink__` and attaches directed edges from each destination sink to the super-sink with infinite capacity.
2. **Residual Graph**:
   For every directed edge (u, v) with capacity C and current flow f, the residual graph maintains:
   - Forward residual capacity: C_f(u, v) = C(u, v) - f(u, v) (remaining capacity).
   - Backward residual capacity: C_f(v, u) = f(u, v) (allows "undoing" flow).
3. **Edmonds-Karp vs Ford-Fulkerson**:
   - **Edmonds-Karp**: Finds augmenting paths using **Breadth-First Search (BFS)**. This guarantees the shortest augmenting path in number of edges, achieving O(|V| * |E|^2) time complexity.
   - **Ford-Fulkerson**: Finds augmenting paths using **Depth-First Search (DFS)**. Time complexity is O(|E| * f_max).
4. **Min-Cut Extraction**:
   After maximum flow is achieved, no augmenting path remains. We run a BFS on the residual graph starting from the source to find all nodes S reachable via edges with residual capacity > 0. The remaining nodes are T = V \ S.
   The **Min-Cut** consists of all original directed edges (u, v) where u in S and v in T. By the **Max-Flow Min-Cut Theorem**, the sum of capacities of these min-cut edges equals the maximum flow value exactly.

#### Classes & Functions:
- **`MaxFlowResult`**:
  - `max_flow: float`: Total throughput achieved in Mbps.
  - `edge_flows: Dict[Tuple[str, str], float]`: Actual flow allocated on each edge.
  - `augmenting_paths: int`: Number of augmentation rounds performed.
  - `operations: int`: Number of edge inspections performed.
  - `compute_time_ms: float`: Computation wall-clock time in milliseconds.
  - `min_cut_edges: List[Tuple[str, str]]`: The bottleneck edge set.
  - `min_cut_capacity: float`: Sum of capacities of the min-cut edges.
  - `to_dict() -> Dict[str, Any]`: JSON-serializable representation.
- **`edmonds_karp(graph: Graph, source: str, sinks: Union[str, List[str]]) -> MaxFlowResult`**:
  Runs Edmonds-Karp with BFS.
- **`ford_fulkerson(graph: Graph, source: str, sinks: Union[str, List[str]]) -> MaxFlowResult`**:
  Runs Ford-Fulkerson with DFS.
- **`compute_max_flow(graph, source, sinks, algo="edmonds_karp")`**:
  Unified wrapper routing to the requested algorithm.
- **`find_network_bottleneck(graph: Graph, source: Optional[str] = None, sinks: Optional[List[str]] = None) -> Dict[str, Any]`**:
  Automatically selects the default origin and edge servers, runs max flow, extracts the min-cut edges, and formats an operational bottleneck diagnostic report.

---

## 6. Deep Dive: Business Logic & Services (`services/`)

The `services/` package separates the web layer (`dashboard/app.py`) and agent layer (`copilot/`) from direct graph manipulation.

### `services/network_service.py`
Acts as the single point of truth for active topologies, state management, and logging.

- **`get_active_topology_entry(session_id: str) -> Dict[str, Any]`**:
  Returns the active session container (creates default CDN topology with `seed=42` if uninitialized).
- **`get_active_graph(session_id: str) -> Graph`**:
  Returns the live `Graph` instance for the session.
- **`set_active_graph(graph: Graph, name: str, session_id: str)`**:
  Replaces the active session graph (e.g. after uploading a custom topology).
- **`list_nodes(graph=None, node_type=None, session_id="default") -> List[Dict[str, Any]]`**:
  Returns serialized node list, optionally filtered by type.
- **`get_metrics(graph=None, session_id="default") -> Dict[str, Any]`**:
  Computes health statistics: node count, edge count, node type distribution, average link latency, and total network bandwidth capacity.
- **`shortest_path(source: str, algo: str = "bellman_ford", session_id: str = "default") -> Dict[str, Any]`**:
  Computes the lowest-latency path from `source` to the nearest edge server, logs a structured event to `EventStore`, and returns path nodes, edge objects, hops, latency, and operations.
- **`compare_algorithms(source: str, session_id: str = "default") -> Dict[str, Any]`**:
  Runs both Bellman-Ford and Floyd-Warshall on the identical source, compares computed paths and latencies for 100% agreement, and returns side-by-side performance metrics.
- **`kill_edge(edge_id: Optional[str] = None, u: Optional[str] = None, v: Optional[str] = None, session_id: str = "default") -> Dict[str, Any]`**:
  Destructively removes a link from the active graph to simulate physical fiber cuts. Logs `link_failure` event to `EventStore`.
- **`heal_edge(u: str, v: str, latency: float = 20.0, bandwidth_capacity: float = 1000.0, bidirectional: bool = True, session_id: str = "default") -> Dict[str, Any]`**:
  Restores a previously severed link.
- **`reset_network(session_id: str = "default") -> Dict[str, Any]`**:
  Destructively resets the active topology back to the default pristine sample CDN. Logs `network_reset` event.
- **`what_if(remove_nodes: Optional[List[str]] = None, remove_edges: Optional[List[str]] = None, source: Optional[str] = None, session_id: str = "default") -> Dict[str, Any]`**:
  **Hypothetical Outage Simulator**: Clones the graph via `g.clone()`, applies the proposed node/edge removals to the isolated clone, evaluates routing before and after the failure, measures latency delta and hop increase, and logs a `what_if` event. **The live network is completely untouched.**
- **`max_flow(source: Optional[str] = None, sinks: Optional[List[str]] = None, algo: str = "edmonds_karp", session_id: str = "default") -> Dict[str, Any]`**:
  Executes max flow calculation on the active network and logs `max_flow_computation` to the event store.
- **`find_bottleneck(source: Optional[str] = None, sinks: Optional[List[str]] = None, session_id: str = "default") -> Dict[str, Any]`**:
  Identifies saturated min-cut bottleneck links on the live network.

---

### `services/topology_service.py`
Enforces strict input validation, row-numbered error reporting, and safe parsing for uploaded network topologies.

- **Security & Limits**:
  - Max 200 nodes, max 2000 edges, max 1MB file payload.
  - **No `eval()` or `pickle`**: Uses pure `json.loads` and standard library `csv.DictReader`.
- **Validation Rules**:
  - Row-numbered reporting: Returns exact row numbers on errors (e.g. `"Row 14: Invalid node_type super_server"`).
  - Duplicate node ID checks.
  - Missing edge endpoint checks (e.g. edge refers to node `edge_99` which does not exist).
  - Negative capacity checks (bandwidth < 0).
  - Structural assertions: Topology must contain at least 1 origin, 1 edge server, and 1 user region.
  - Warnings on negative latency links or disconnected graph components.
- **Functions**:
  - **`validate_and_build_topology(nodes_data, edges_data, topology_name) -> Tuple[Graph, str, List[str]]`**: Validates parsed records, builds a `Graph`, and returns `(graph, name, warnings)`.
  - **`parse_json_topology(json_str: str) -> Tuple[Graph, str, List[str]]`**: Parses JSON payload `{"nodes": [...], "edges": [...]}`.
  - **`parse_csv_topology(nodes_csv: str, edges_csv: str) -> Tuple[Graph, str, List[str]]`**: Parses two CSV files (nodes and edges).
  - **`generate_template_csv() -> Tuple[str, str]`**: Generates starter template CSV strings for download.
  - **`generate_template_json() -> str`**: Generates starter template JSON string.
  - **`cleanup_expired_sessions(max_age_seconds: int = 7200)`**: Garbage collects abandoned user sessions.

---

### `services/postmortem_service.py`
Automates post-incident reporting for network failures.

- **`generate_postmortem(event_id: Optional[str] = None, session_id: str = "default", time_window_minutes: int = 60, db_path: str = "network_events.db") -> Dict[str, Any]`**:
  1. Queries the SQLite `EventStore` for the specified incident `event_id` (or finds the most recent link failure).
  2. Queries all related events in that session within the preceding `time_window_minutes`.
  3. Formats an enterprise-grade incident postmortem report in Markdown format with 5 required sections:
     - **Summary**: Incident ID, timestamp, component affected, duration.
     - **Timeline**: Chronological breakdown of events logged in the database.
     - **Impact**: Before/after latency, severed routes, disconnected user regions.
     - **Root Cause Analysis**: Algorithmic explanation of why path failure occurred.
     - **Preventative Mitigations**: Proactive steps to reinforce link capacity.
  4. Returns the generated Markdown and the exact event ID.

---

### `services/mitigation_service.py`
Autonomous network remediation and simulation engine.

- **Concept**: When a network experiences an outage or congestion, operators want to know what changes (e.g. adding a backup link, increasing bandwidth) will fix the problem with the highest impact and lowest cost.
- **Simulation on Graph Copies**: Candidates are simulated entirely on deep copies of the graph. The live network is preserved.
- **Deterministic Ranking**: Changes are ranked by measured metric deltas (e.g. change in throughput, change in latency). Invalid proposals (e.g. adding an edge to a non-existent node) are rejected.
- **Functions**:
  - **`_compute_graph_metrics(graph) -> Dict[str, float]`**: Measures max flow throughput, min-cut capacity, min-cut edge count, and average user latency on a graph instance.
  - **`get_default_candidates_for_goal(goal: str, graph: Graph) -> List[Dict[str, Any]]`**: Proposes heuristic candidate actions depending on the goal (`"maximize throughput"`, `"minimize latency"`, `"resolve bottleneck"`).
  - **`simulate_mitigation(graph: Graph, candidate: Dict[str, Any]) -> Dict[str, Any]`**: Clones graph, applies candidate, measures delta, returns impact.
  - **`propose_and_simulate_mitigations(goal: str, session_id: str = "default", candidates: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]`**: Orchestrates candidate simulation and sorts them deterministically by benefit.
  - **`apply_mitigation(action: Dict[str, Any], session_id: str = "default", confirmed: bool = False) -> Dict[str, Any]`**: Applies the selected mitigation to the live active network upon explicit confirmation.

---

## 7. Deep Dive: Event Store & Persistence (`storage/`)

### `storage/event_store.py`
Provides structured event logging into SQLite (`network_events.db`). Every routing query, link failure, what-if simulation, and max flow run is recorded for auditing and RAG retrieval.

- **Database Table (`events`)**:
  - `id TEXT PRIMARY KEY`: Unique event ID (e.g. `evt_7a8b9c10d`).
  - `timestamp TEXT`: ISO 8601 UTC timestamp.
  - `session_id TEXT`: Session identifier.
  - `type TEXT`: Event type (`"shortest_path"`, `"link_failure"`, `"what_if"`, etc.).
  - `topology_name TEXT`: Name of the active topology when event occurred.
  - `inputs TEXT`: JSON-serialized input parameters.
  - `results TEXT`: JSON-serialized algorithm results.
  - `ops_count INTEGER`: Operations performed by algorithm.
  - `compute_time_ms REAL`: Runtime in milliseconds.
- **Methods on `EventStore`**:
  - `log_event(session_id, event_type, topology_name, inputs, results, ops_count, compute_time_ms) -> NetworkEvent`: Records a new event.
  - `get_event(event_id: str) -> Optional[NetworkEvent]`: Retrieves a single event by ID.
  - `list_events(session_id: Optional[str] = None, event_type: Optional[str] = None, limit: int = 50) -> List[NetworkEvent]`: Retrieves recent events.
  - `search_events(query: str, session_id: Optional[str] = None, limit: int = 10) -> List[NetworkEvent]`: Simple text query over events.
  - `clear_session(session_id: str)`: Deletes events for a session.
- **`get_event_store(db_path: str = "network_events.db") -> EventStore`**: Singleton factory.

---

## 8. Deep Dive: RAG Knowledge Base & Semantic Search (`rag/`)

NetPilot uses Retrieval-Augmented Generation (RAG) to ground its incident explanations in real networking operational runbooks and past outage events.

### `rag/embedder.py`

#### 1. `DeterministicFakeEmbedder`
An offline, zero-dependency embedder designed for predictable testing and offline deployment:
- Projects text into a 64-dimensional unit-normalized vector.
- Maps domain-specific keyword clusters (e.g., *link failure*, *congestion*, *outage*, *latency*, *topology*) to specific dimensional buckets.
- Guarantees that semantically related terms like "severed link" and "link failure" yield high cosine similarity (> 0.8) without requiring internet or PyTorch.

#### 2. `OpenAIEmbedder`
Uses remote OpenAI-compatible embedding endpoints (e.g. `text-embedding-3-small`) if configured.

#### 3. `get_embedder() -> BaseEmbedder`
Instantiates `OpenAIEmbedder` if `EMBEDDING_API_KEY` is present; otherwise falls back to `DeterministicFakeEmbedder`.

---

### `rag/vector_store.py`

- **Database Table (`documents`)**:
  - `id TEXT PRIMARY KEY`: Chunk ID (e.g. `runbook_link_failure_chunk_0`).
  - `doc_type TEXT`: `runbook` or `event`.
  - `title TEXT`: Title of document.
  - `content TEXT`: Chunk text.
  - `chunk_path TEXT`: File source or database event reference.
  - `embedding_json TEXT`: JSON array storing the embedding vector.
- **`cosine_similarity(vec1: List[float], vec2: List[float]) -> float`**:
  Computes normalized dot product in pure Python.
- **`VectorStore` Methods**:
  - `_init_db()`: Initializes table and index `idx_doc_type`.
  - `add_document(id, doc_type, title, content, chunk_path, embedding)`: Upserts a document chunk.
  - `search(query: str, doc_type: Optional[str] = None, limit: int = 3) -> List[Dict[str, Any]]`: Embeds query, compares against stored vectors using `cosine_similarity`, and returns top-k matches with similarity scores.
  - `sync_runbooks(runbooks_dir: str)`: Reads all markdown runbooks in `runbooks/`, splits them into structured sections, and indexes them.
  - `sync_events(limit: int = 25)`: Ingests recent events from `EventStore` so past outages are searchable.
  - `count_documents() -> Dict[str, int]`: Returns total counts broken down by `runbook` and `event`.
- **`get_vector_store(db_path, embedder) -> VectorStore`**: Factory function.

---

## 9. Deep Dive: NetPilot AI Copilot (`copilot/`)

The `copilot/` package implements the LLM agent, tool execution router, safety guardrails, and anti-hallucination verification.

### `copilot/llm_provider.py`
Unified client interface supporting multiple LLM backends:

- **Built-in `load_dotenv()`**:
  Pure standard-library parser that reads `.env` on module import, stripping comments and populating `os.environ`. No external `python-dotenv` required.
- **`BaseLLMProvider`**:
  Abstract base class defining `chat_completion(messages, tools) -> LLMResponse`.
- **`GroqOpenAIProvider`**:
  High-speed production provider using standard `urllib.request`.
  - Automatically targets `https://api.groq.com/openai/v1` when `GROQ_API_KEY` is detected.
  - Auto-configures accessible models (`openai/gpt-oss-120b`, `llama-3.1-8b-instant`, or `GROQ_MODEL`).
  - Supports standard OpenAI function calling tool schemas.
- **`FakeLLMProvider`**:
  Offline deterministic mock provider used for test suites and evaluation dry-runs. Emulates tool calling based on regex keywords.
- **`get_llm_provider() -> Optional[BaseLLMProvider]`**:
  Returns the active provider or `None` if no keys are present.
- **`get_active_provider_name() -> str`**:
  Returns `groq`, `openai`, or `fake`.

---

### `copilot/guardrails.py`
Enforces API quotas and operational safety:

- **`is_copilot_enabled() -> bool`**:
  Global administrative kill switch via `COPILOT_ENABLED` env var (`"true"` / `"false"`).
- **`check_rate_limit(session_id: str) -> Tuple[bool, Optional[int]]`**:
  Sliding 60-second window rate limiter per session (default: 10 requests/min). Returns `(allowed, retry_after)`.
- **`check_daily_token_budget() -> Tuple[bool, int, int]`**:
  Tracks cumulative token usage for the UTC day against `DAILY_TOKEN_BUDGET` (default: 100,000 tokens). Prevents unexpected billing surprises.
- **`record_tokens_consumed(tokens: int)`**:
  Accumulates tokens into daily consumption tracker.
- **`redact_sensitive_info(text: str) -> str`**:
  Sanitizes output strings, redacting API keys (`gsk_...`, `sk-...`).

---

### `copilot/verifier.py`
Provides automated anti-hallucination guardrails:

- **`extract_numbers_from_text(text: str) -> List[float]`**:
  Extracts all standalone floating-point and integer numbers from a text response using regex.
- **`extract_numbers_from_tool_results(tool_results: Any) -> Set[float]`**:
  Recursively crawls nested tool output dictionaries and lists to harvest every single ground-truth numeric value.
- **`verify_number_grounding(answer_text: str, tool_results: List[Dict[str, Any]], tolerance: float = 0.01) -> Tuple[bool, List[float], str]`**:
  Compares numbers mentioned by the LLM against the tool harvest.
  If the LLM invents numbers (e.g. claiming latency is `999.9 ms` when the tool returned `14.5 ms`), the verifier appends a prominent alert:
  > `⚠️ Verification Notice: Ungrounded numbers detected not present in tool results: [999.9]. Always inspect tool output.`
- **`verify_event_id_grounding(answer_text: str, event_store: EventStore) -> Tuple[bool, List[str]]`**:
  Verifies that any event ID cited by the model actually exists in `network_events.db`.

---

### `copilot/tools.py`
Defines tool schemas and handles safe execution dispatching:

- **Pydantic Argument Schemas**:
  - `ShortestPathArgs`: `source: str`, `algo: Optional[Literal["bellman_ford", "floyd_warshall"]]`.
  - `CompareAlgorithmsArgs`: `source: str`.
  - `KillEdgeArgs`: `edge_id: Optional[str]`, `u: Optional[str]`, `v: Optional[str]`, `confirmed: Optional[bool]`.
  - `ResetNetworkArgs`: `confirmed: Optional[bool]`.
  - `WhatIfArgs`: `remove_nodes: Optional[List[str]]`, `remove_edges: Optional[List[str]]`, `source: Optional[str]`.
  - `MaxFlowArgs`: `source: Optional[str]`, `sinks: Optional[List[str]]`, `algo: Optional[Literal["edmonds_karp", "ford_fulkerson"]]`.
  - `FindBottleneckArgs`: `source: Optional[str]`, `sinks: Optional[List[str]]`.
  - `GetMetricsArgs`: Empty.
  - `ListNodesArgs`: `node_type: Optional[Literal["origin", "edge_server", "user_region", "transit"]]`.
  - `SearchHistoryArgs`: `query: str`, `doc_type: Optional[Literal["event", "runbook"]]`, `limit: Optional[int]`.
  - `GeneratePostmortemArgs`: `event_id: Optional[str]`, `time_window_minutes: Optional[int]`.
  - `ProposeMitigationsArgs`: `goal: str`.
- **`COPILOT_TOOLS_OPENAI_SPEC`**:
  OpenAPI 3.0 specification exported to LLM providers. Configured with nullable types (`type: ["string", "null"]`) to maintain strict compatibility with Groq and OpenAI validators.
- **Destructive Action Safety Confirmation**:
  Operations that modify the live network (`kill_edge`, `reset_network`) enforce a confirmation gate. If called with `confirmed=False`, the dispatcher pauses execution and returns a confirmation request object to the user interface.
- **`execute_tool_call(function_name: str, raw_arguments: Dict[str, Any], session_id: str) -> Tuple[Dict[str, Any], bool]`**:
  Validates arguments with Pydantic and invokes the corresponding function in `services/network_service.py`.

---

### `copilot/agent.py`
Implements the multi-step ReAct agent loop:

- **`run_copilot_chat(message: str, session_id: str = "default", history: Optional[List[Dict[str, Any]]] = None, confirm_action: Optional[Dict[str, Any]] = None, custom_provider: Optional[BaseLLMProvider] = None) -> Dict[str, Any]`**:
  1. Checks guardrails (is enabled, rate limits, token budget).
  2. If `confirm_action` is provided by user, executes the destructive tool immediately.
  3. Prepares system instructions emphasizing that NetPilot is a network diagnostic assistant that must always use tools to compute values.
  4. Manages multi-turn tool calling loop (up to `MAX_TOOL_STEPS = 5` iterations):
     - Sends user prompt and tool specs to the provider.
     - If the model generates tool calls, dispatches them via `execute_tool_call`.
     - Appends tool results as `{"role": "tool", "content": ...}` and calls model again.
  5. Runs `verify_number_grounding` on the model's final response text.
  6. Records token usage and returns structured output containing `answer`, `tools_used`, `grounding_verified`, and `latency_ms`.

---

## 10. Deep Dive: Web Application Backend (`dashboard/`)

### `dashboard/app.py`
Exposes REST API endpoints and serves the visual interface:

#### Helper Functions:
- `_get_session_id() -> str`: Extracts session ID from `X-Session-ID` header or defaults to `default`.
- `sanitize_text(text: Any, max_len: int = 100) -> str`: HTML-escapes strings to prevent cross-site scripting (XSS).
- `format_graph_for_vis(g: Graph) -> Dict[str, Any]`: Converts `Graph` into Vis.js node and edge format with distinct geometric shapes and colors:
  - Origin: Yellow diamond (`#ffb703`).
  - Edge Server: Cyan hexagon (`#00b4d8`).
  - Transit Relay: Purple dot (`#8b5cf6`).
  - User Region: Green dot (`#10b981`).

#### HTTP Routes:
| Route | Method | Purpose |
| :--- | :--- | :--- |
| `/` | `GET` | Serves main single-page dashboard. |
| `/api/network` | `GET` | Returns Vis.js network JSON for active session. |
| `/api/route` | `POST` | Computes shortest path from selected user region using Bellman-Ford or Floyd-Warshall. |
| `/api/route/compare` | `POST` | Runs both algorithms and returns side-by-side verification table. |
| `/api/edge/fail` | `POST` | Destructively severs an edge to simulate failure. |
| `/api/edge/heal` | `POST` | Restores a previously severed edge. |
| `/api/network/reset` | `POST` | Resets session network back to default pristine CDN. |
| `/api/max-flow` | `POST` | Computes maximum bandwidth throughput from origin to edge servers. |
| `/api/bottleneck` | `GET` | Identifies saturated min-cut bottleneck links. |
| `/api/topology/upload` | `POST` | Uploads and validates custom JSON or CSV network topologies. |
| `/api/topology/template` | `GET` | Downloads starter JSON or CSV template topologies. |
| `/api/copilot/chat` | `POST` | Chat endpoint for NetPilot AI Copilot with streaming tool status. |
| `/api/postmortem/generate` | `POST` | Generates a Markdown incident postmortem. |
| `/api/mitigations/propose` | `POST` | Proposes and simulates candidate network improvements. |
| `/api/mitigations/apply` | `POST` | Applies a confirmed mitigation to the live network. |
| `/api/llmops/stats` | `GET` | Returns token usage, RAG document counts, and benchmark metrics. |
| `/api/llmops/plot` | `GET` | Serves comparison plot figure for the LLMOps panel. |

---

## 11. Deep Dive: Offline Evaluation Benchmark (`eval/`)

Milestone M8 introduced an automated evaluation harness to quantitatively benchmark NetPilot against baselines.

### `eval/generator.py`
Programmatically generates **50 comprehensive test questions** across 7 distinct operational categories:
1. `shortest_path` (routing latency, hops, path sequences)
2. `compare_algorithms` (Bellman-Ford vs Floyd-Warshall agreement)
3. `what_if` (counterfactual failure impact)
4. `max_flow` (throughput and augmentation counts)
5. `find_bottleneck` (min-cut saturated edge identification)
6. `search_history` (RAG incident retrieval and runbook advice)
7. `destructive_actions` (safety confirmation gating)

- **Ground Truth**: Every question template executes our Python engines directly on the active graph to generate exact numeric ground truth.
- **Dataset Split**: 15 development templates and 35 evaluation test templates. Generates 2-3 natural language phrasings per template.

---

### `eval/evaluator.py`
Evaluates **4 distinct system configurations** over 3 runs on the 35 test templates (**420 total queries**):

1. **Config 1: Plain LLM**: Receives the entire network topology as raw text in the prompt; no tools, no RAG.
2. **Config 2: LLM + RAG**: Access to runbook retrieval only; no execution tools.
3. **Config 3: LLM + Tools**: Access to scratch Python engines; no RAG or grounding verifier.
4. **Config 4: Full NetPilot**: Tools + RAG + Number Grounding Verifier.

#### Strict Scoring Rules:
- **Numeric values**: Must match ground truth within **1% relative tolerance**.
- **Sets and integers**: Must match **exactly**.
- **Destructive operations**: Must request explicit user confirmation; fail if executed without confirmation.
- **Hallucinations**: Any number in the answer not present in the tool results or context is counted as a hallucination.

#### CLI Arguments:
- `--dry-run`: Runs the evaluation instantly using `FakeLLMProvider` (consumes zero tokens).
- `--runs N`: Number of iterations per configuration (default: 3).
- `--limit N`: Restricts questions to the first N templates for rapid testing.
- `--resume`: Resumes from saved partial results if an API error occurs.

---

## 12. Comprehensive Master Function Directory

A quick reference lookup for every core function across the codebase:

| Function / Class | File Location | Primary Arguments | Description |
| :--- | :--- | :--- | :--- |
| `Node` | `graph/network.py` | `node_id, node_type, label, **metadata` | Class representing a graph node. |
| `Edge` | `graph/network.py` | `u, v, latency, bandwidth_capacity` | Class representing a directed network link. |
| `Graph` | `graph/network.py` | None | Core directed graph data structure. |
| `add_edge` | `graph/network.py` | `u, v, latency, bandwidth, bidirectional` | Adds directed or bidirectional link. |
| `remove_edge` | `graph/network.py` | `u, v, bidirectional` | Deletes link to simulate cable failure. |
| `clone` | `graph/network.py` | None | Returns isolated deep copy of graph. |
| `generate_cdn_topology` | `graph/generator.py` | `num_origins, num_edges, num_users, seed` | Builds standard hierarchical CDN graph. |
| `bellman_ford` | `routing/bellman_ford.py` | `graph, source, detect_negative_cycle` | Computes SSSP and detects negative cycles. |
| `find_best_edge_server_bf` | `routing/bellman_ford.py` | `graph, user_region_id` | Finds closest edge server via Bellman-Ford. |
| `floyd_warshall` | `routing/floyd_warshall.py` | `graph, detect_negative_cycle` | Computes APSP matrix and next-hop paths. |
| `find_best_edge_server_fw` | `routing/floyd_warshall.py` | `graph, user_region_id` | Finds closest edge server via Floyd-Warshall. |
| `edmonds_karp` | `routing/max_flow.py` | `graph, source, sinks` | Computes max bandwidth using BFS. |
| `ford_fulkerson` | `routing/max_flow.py` | `graph, source, sinks` | Computes max bandwidth using DFS. |
| `find_network_bottleneck` | `routing/max_flow.py` | `graph, source, sinks` | Identifies saturated min-cut bottleneck links. |
| `shortest_path` | `services/network_service.py` | `source, algo, session_id` | Service computing shortest path and logging event. |
| `compare_algorithms` | `services/network_service.py` | `source, session_id` | Validates BF and FW path agreement. |
| `what_if` | `services/network_service.py` | `remove_nodes, remove_edges, source` | Simulates hypothetical outage on graph copy. |
| `validate_and_build_topology` | `services/topology_service.py`| `nodes_data, edges_data, name` | Validates custom topology with row errors. |
| `generate_postmortem` | `services/postmortem_service.py`| `event_id, session_id, time_window` | Generates incident postmortem report in Markdown. |
| `propose_and_simulate_mitigations`| `services/mitigation_service.py`| `goal, session_id` | Proposes and simulates candidate network fixes. |
| `EventStore` | `storage/event_store.py` | `db_path` | SQLite event store logging all telemetry. |
| `cosine_similarity` | `rag/vector_store.py` | `vec1, vec2` | Computes pure-Python vector cosine similarity. |
| `VectorStore` | `rag/vector_store.py` | `db_path, embedder` | SQLite vector search database. |
| `verify_number_grounding` | `copilot/verifier.py` | `answer_text, tool_results` | Detects ungrounded/hallucinated numbers in LLM answers. |
| `check_rate_limit` | `copilot/guardrails.py` | `session_id` | Sliding 60-second rate limiter per session. |
| `execute_tool_call` | `copilot/tools.py` | `function_name, raw_arguments` | Pydantic validation and tool execution router. |
| `run_copilot_chat` | `copilot/agent.py` | `message, session_id, history` | Multi-step agentic tool-calling ReAct loop. |

---

## 13. How to Run, Test & Debug

### 1. Starting the Web Server
```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. (Optional) Set your Groq API key for live AI Copilot
export GROQ_API_KEY="gsk_your_groq_key_here"

# 3. Start Flask application
python dashboard/app.py
```
Open your browser at **`http://localhost:5000`**.

### 2. Running Automated Tests
The repository includes 67 unit and regression tests covering all algorithms, services, APIs, and copilot guardrails:
```bash
pytest -v
```
*Expected result: 67 passed in ~2.5 seconds.*

### 3. Running Complexity Benchmarks
To measure empirical operation counts and generate runtime scaling curves:
```bash
python benchmarks/benchmark.py
```
*Generates `complexity_benchmark.png` illustrating O(|V| * |E|) vs O(|V|^3) scaling.*

### 4. Running the Offline AI Evaluation Harness
To benchmark the 4 AI Copilot configurations:
```bash
# Fast dry-run (zero token cost)
python -m eval.evaluator --dry-run --runs 1 --limit 5

# Full test run (if API key is configured)
python -m eval.evaluator --runs 3
```
Outputs are written to `eval/results/eval_results.csv` and `eval/results/eval_summary.md`.
