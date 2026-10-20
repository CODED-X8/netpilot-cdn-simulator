"""Empirical complexity benchmarking for Bellman-Ford vs Floyd-Warshall.

Measures wall-clock time and operation count across varying graph sizes N = [10, 20, 50, 100, 150, 200],
averaging results across multiple random topology trials. Generates:
- CSV results in benchmarks/results/benchmark_results.csv
- Comparative visual plot in benchmarks/results/complexity_benchmark.png
"""

import os
import sys
import time
import csv
from typing import List, Dict, Any

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from graph.generator import generate_random_benchmark_graph
from routing.bellman_ford import bellman_ford
from routing.floyd_warshall import floyd_warshall
from routing.dijkstra import dijkstra


def run_benchmark(
    node_counts: List[int] = [10, 20, 50, 80, 120, 160, 200],
    edge_density: float = 0.25,
    trials_per_n: int = 3,
    output_dir: str = "benchmarks/results",
) -> List[Dict[str, Any]]:
    """Execute benchmark over varying node counts and write CSV and plots."""
    os.makedirs(output_dir, exist_ok=True)
    results: List[Dict[str, Any]] = []

    print(f"{'N':>5} | {'|E|':>6} | {'BF Time (ms)':>12} | {'BF Ops':>10} | {'FW Time (ms)':>12} | {'FW Ops':>12} | {'Dijk Time':>10} | {'Dijk Ops':>10} | {'AP-Dijk Time':>12} | {'AP-Dijk Ops':>11}")
    print("-" * 120)

    for n in node_counts:
        bf_times = []
        bf_ops_list = []
        fw_times = []
        fw_ops_list = []
        dijk_times = []
        dijk_ops_list = []
        ap_dijk_times = []
        ap_dijk_ops_list = []
        edge_counts = []

        for trial in range(trials_per_n):
            seed = 1000 * n + trial
            g = generate_random_benchmark_graph(
                num_nodes=n,
                edge_density=edge_density,
                seed=seed,
            )
            e = g.edge_count()
            edge_counts.append(e)
            source_node = list(g.nodes.keys())[0]

            # 1. Benchmark Bellman-Ford (Single-Source)
            t0 = time.perf_counter()
            bf_res = bellman_ford(g, source=source_node, early_stopping=False)
            t1 = time.perf_counter()
            bf_times.append((t1 - t0) * 1000.0)  # ms
            bf_ops_list.append(bf_res.operations)

            # 2. Benchmark Floyd-Warshall (All-Pairs)
            t0 = time.perf_counter()
            fw_res = floyd_warshall(g, detect_negative_cycle=True)
            t1 = time.perf_counter()
            fw_times.append((t1 - t0) * 1000.0)  # ms
            fw_ops_list.append(fw_res.operations)

            # 3. Benchmark Dijkstra (Single-Source Heap)
            t0 = time.perf_counter()
            dijk_res = dijkstra(g, source=source_node)
            t1 = time.perf_counter()
            dijk_times.append((t1 - t0) * 1000.0)  # ms
            dijk_ops_list.append(dijk_res.operations)

            # 4. Benchmark All-Pairs Dijkstra (Apples-to-Apples with Floyd-Warshall APSP)
            t0 = time.perf_counter()
            ap_dijk_ops = 0
            for u in g.nodes:
                d_res = dijkstra(g, source=u)
                ap_dijk_ops += d_res.operations
            t1 = time.perf_counter()
            ap_dijk_times.append((t1 - t0) * 1000.0)  # ms
            ap_dijk_ops_list.append(ap_dijk_ops)

        avg_e = int(round(sum(edge_counts) / len(edge_counts)))
        avg_bf_time = sum(bf_times) / len(bf_times)
        avg_bf_ops = int(round(sum(bf_ops_list) / len(bf_ops_list)))
        avg_fw_time = sum(fw_times) / len(fw_times)
        avg_fw_ops = int(round(sum(fw_ops_list) / len(fw_ops_list)))
        avg_dijk_time = sum(dijk_times) / len(dijk_times)
        avg_dijk_ops = int(round(sum(dijk_ops_list) / len(dijk_ops_list)))
        avg_ap_dijk_time = sum(ap_dijk_times) / len(ap_dijk_times)
        avg_ap_dijk_ops = int(round(sum(ap_dijk_ops_list) / len(ap_dijk_ops_list)))

        theo_ve_mean = int(round(sum(n * e for e in edge_counts) / len(edge_counts)))

        row = {
            "N": n,
            "Edges": avg_e,
            "BF_Time_ms": round(avg_bf_time, 3),
            "BF_Operations": avg_bf_ops,
            "FW_Time_ms": round(avg_fw_time, 3),
            "FW_Operations": avg_fw_ops,
            "Dijk_Time_ms": round(avg_dijk_time, 3),
            "Dijk_Operations": avg_dijk_ops,
            "AP_Dijk_Time_ms": round(avg_ap_dijk_time, 3),
            "AP_Dijk_Operations": avg_ap_dijk_ops,
            "Theoretical_O_VE": theo_ve_mean,
            "Theoretical_O_V3": n ** 3,
            "Theoretical_O_E_log_V": int(round(avg_e * math.log2(max(2, n)))),
        }
        results.append(row)

        print(
            f"{n:>5} | {avg_e:>6} | {avg_bf_time:>12.2f} | {avg_bf_ops:>10} | "
            f"{avg_fw_time:>12.2f} | {avg_fw_ops:>12} | {avg_dijk_time:>10.2f} | {avg_dijk_ops:>10} | "
            f"{avg_ap_dijk_time:>12.2f} | {avg_ap_dijk_ops:>11}"
        )

    # Save CSV
    csv_path = os.path.join(output_dir, "benchmark_results.csv")
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"\n[+] Saved CSV results to: {csv_path}")

    # Generate Matplotlib Plot
    plot_path = os.path.join(output_dir, "complexity_benchmark.png")
    plot_benchmark_results(results, plot_path)
    print(f"[+] Saved Benchmark Chart to: {plot_path}")

    return results


def plot_benchmark_results(results: List[Dict[str, Any]], output_path: str):
    """Plot empirical wall-clock time and operations count comparison."""
    n_vals = [r["N"] for r in results]
    bf_times = [r["BF_Time_ms"] for r in results]
    fw_times = [r["FW_Time_ms"] for r in results]
    dijk_times = [r["Dijk_Time_ms"] for r in results]
    ap_dijk_times = [r.get("AP_Dijk_Time_ms", 0) for r in results]
    bf_ops = [r["BF_Operations"] for r in results]
    fw_ops = [r["FW_Operations"] for r in results]
    dijk_ops = [r["Dijk_Operations"] for r in results]
    ap_dijk_ops = [r.get("AP_Dijk_Operations", 0) for r in results]
    theo_ve = [r["Theoretical_O_VE"] for r in results]
    theo_v3 = [r["Theoretical_O_V3"] for r in results]
    theo_e_log_v = [r.get("Theoretical_O_E_log_V", 0) for r in results]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=300)
    plt.subplots_adjust(wspace=0.25)

    # ------------------ Subplot 1: Wall-Clock Execution Time ------------------
    ax1.plot(n_vals, fw_times, "o-", color="#d9534f", linewidth=2.2, label="Floyd-Warshall (APSP $O(V^3)$)")
    ax1.plot(n_vals, ap_dijk_times, "d-", color="#8b5cf6", linewidth=2.2, label="All-Pairs Dijkstra ($V \\times O((V+E)\\log V)$)")
    ax1.plot(n_vals, bf_times, "s-", color="#0275d8", linewidth=2.2, label="Bellman-Ford (SSSP $O(V \\cdot E)$)")
    ax1.plot(n_vals, dijk_times, "^-", color="#10b981", linewidth=2.2, label="Dijkstra (SSSP Heap $O(E \\log V)$)")
    ax1.set_title("Empirical Execution Time vs Graph Size (N)", fontsize=13, fontweight="bold", pad=12)
    ax1.set_xlabel("Number of Nodes |V|", fontsize=11, fontweight="medium")
    ax1.set_ylabel("Execution Time (ms)", fontsize=11, fontweight="medium")
    ax1.set_yscale("log")
    ax1.grid(True, which="both", linestyle="--", alpha=0.5)
    ax1.legend(loc="upper left", frameon=True, fontsize=8.5)

    # Annotate complexities
    ax1.text(
        0.05, 0.48,
        "Floyd-Warshall (APSP): $O(V^3)$\nAll-Pairs Dijkstra: $V \\times O((V+E) \\log V)$\nBellman-Ford (SSSP): $O(V \\cdot E)$\nDijkstra (SSSP): $O((V+E) \\log V)$",
        transform=ax1.transAxes,
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa", edgecolor="#ced4da", alpha=0.9),
        fontsize=8.5,
    )

    # ------------------ Subplot 2: Empirical Operation Counts ------------------
    ax2.plot(n_vals, fw_ops, "o-", color="#d9534f", linewidth=2.2, label="Measured FW Ops ($V^3$)")
    ax2.plot(n_vals, theo_v3, "--", color="#8b0000", alpha=0.6, label="Theoretical $V^3$")
    ax2.plot(n_vals, ap_dijk_ops, "d-", color="#8b5cf6", linewidth=2.2, label="Measured All-Pairs Dijk Ops")
    ax2.plot(n_vals, bf_ops, "s-", color="#0275d8", linewidth=2.2, label="Measured BF Ops ($V \\cdot E$)")
    ax2.plot(n_vals, theo_ve, "--", color="#003366", alpha=0.6, label="Theoretical $V \\cdot E$ (Exact Mean)")
    ax2.plot(n_vals, dijk_ops, "^-", color="#10b981", linewidth=2.2, label="Measured Dijkstra SSSP Ops")
    ax2.set_title("Elementary Operations vs Graph Size (N)", fontsize=13, fontweight="bold", pad=12)
    ax2.set_xlabel("Number of Nodes |V|", fontsize=11, fontweight="medium")
    ax2.set_ylabel("Operation Count (Comparisons & Heap)", fontsize=11, fontweight="medium")
    ax2.set_yscale("log")
    ax2.grid(True, which="both", linestyle="--", alpha=0.5)
    ax2.legend(loc="upper left", frameon=True, fontsize=8.5)

    plt.suptitle("Mini CDN Routing Engine: Empirical vs Theoretical Complexity Analysis", fontsize=15, fontweight="bold", y=0.98)
    plt.tight_layout()
    plt.savefig(output_path, bbox_inches="tight")
    plt.close()


if __name__ == "__main__":
    run_benchmark()
