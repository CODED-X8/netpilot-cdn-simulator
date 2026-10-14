# Regional Outage and POP Failover Runbook

Guidance for responding to catastrophic regional data center outages and edge POP collapses.

## Cascading POP Failures
1. A regional outage occurs when an entire edge data center fails (e.g. power, backbone severed).
2. Isolate all incident links connected to the downed edge server using batch simulated link cuts or `what_if` with `remove_nodes`.
3. Check surviving network connectivity to confirm whether user regions remain reachable.

## Regional Failover and User Rehoming
1. Recalculate shortest paths for affected user regions using `shortest_path`.
2. Traffic must automatically shift to the next nearest geo-distributed Edge POP (e.g. US-East shifting to US-Central or EU-West to EU-Central).
3. Verify that the secondary POP has sufficient bandwidth capacity using `max_flow` to prevent cascading secondary collapse.
