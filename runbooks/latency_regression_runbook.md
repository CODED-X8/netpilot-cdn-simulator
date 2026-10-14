# Latency Regression Runbook

Diagnostic workflow for investigating latency spikes and suboptimal routing paths.

## Diagnosing Suboptimal Multi-Hop Routes
1. When user latency spikes by more than 15ms without link failure, investigate multi-hop routing paths.
2. Run `shortest_path` to inspect the complete hop-by-hop node sequence (`routed_path`).
3. Check whether traffic is taking an indirect detour through distant transit nodes rather than direct edge links.

## Algorithm Cross-Verification
1. Execute `compare_algorithms` to cross-validate Bellman-Ford and Floyd-Warshall routing decisions.
2. Verify operation counts and ensure neither engine is encountering negative weight cycles or convergence anomalies.
3. If Floyd-Warshall shows a lower latency path than Bellman-Ford, verify graph relaxation completeness.
