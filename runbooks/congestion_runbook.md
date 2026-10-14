# Congestion and Bottleneck Runbook

Procedures for detecting throughput bottlenecks, link saturation, and min-cut boundaries.

## Detecting Saturated Links
1. Observe bandwidth utilization metrics across core and edge distribution links.
2. Run tool `max_flow` using Edmonds-Karp or Ford-Fulkerson to compute aggregate throughput capacity from origin servers to target edge POPs.

## Identifying Bottlenecks via Min-Cut
1. Run tool `find_bottleneck` to locate the minimum capacity cut-set separating source from sinks.
2. Highlight cut edges (rendered in red in the topology view) to pinpoint critical choke points.
3. Quantify total bottleneck capacity and individual edge constraints.

## Traffic Throttling and Mitigation
1. Redirect latency-tolerant background traffic away from min-cut saturated paths.
2. Increase physical bandwidth allocation or spin up temporary transit links to expand cut capacity.
