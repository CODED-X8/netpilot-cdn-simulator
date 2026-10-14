# Link Failure Runbook

Standard operating procedures for managing, diagnosing, and mitigating severed network links in the CDN backbone.

## Isolating a Severed Link
When a link drops packets or exhibits complete disconnect:
1. Identify the failing edge identifier (e.g. `user_1<->edge_1` or `transit_1<->transit_2`).
2. Run tool `what_if` to evaluate alternative path feasibility and latency delta prior to altering physical topology.
3. If confirmed severed, invoke `kill_edge` to officially remove the link from active routing graphs.

## Rerouting Traffic
1. Trigger Bellman-Ford SSSP (`shortest_path`) for affected user populations to discover the lowest-latency alternative Edge server.
2. Verify if the new route traverses multi-hop transit nodes and record the updated hop count.
3. Compare algorithm performance using `compare_algorithms` to ensure consistent convergence across SSSP and APSP routing tables.

## Verifying Post-Incident Latency
1. Check end-to-end latency via `get_metrics` to ensure aggregate latency SLA has not degraded beyond acceptable operational thresholds (+20ms).
2. If latency exceeds tolerance, assess secondary paths or provision additional transit links.
