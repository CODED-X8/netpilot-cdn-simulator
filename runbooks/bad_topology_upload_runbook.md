# Bad Topology Upload and Rollback Runbook

Protocols for handling invalid topology uploads, corrupted network graphs, and structural partitioning.

## Identifying Broken Topologies
1. When custom topologies fail validation:
   - Check error logs for duplicate node IDs, negative bandwidth capacities, or missing origin servers.
   - Inspect warnings for disconnected user regions or isolated edge clusters.
2. If graph upload caused broken connectivity, user requests will fail with unreachable destination errors.

## Emergency Rollback to Baseline CDN
1. To restore network stability immediately, trigger `reset_network`.
2. This replaces the active topology with the verified default 20-node hierarchical CDN graph.
3. Validate operational recovery by running `get_metrics` (expecting 20 nodes, 80 edges).
