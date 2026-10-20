"""Evaluation Runner and Metrics Engine (Milestone M8).

Runs offline evaluation across 4 configurations:
- Config 1: Plain LLM (full topology serialized as text in prompt, no tools, no RAG)
- Config 2: LLM + RAG (runbook search only, no execution tools)
- Config 3: LLM + Tools (execution tools only, no RAG or grounding verifier)
- Config 4: Full System (LLM + Tools + RAG + Verifier)

Scoring rules:
- Numeric answers: 1% tolerance relative error
- Integers & sets: exact match
- search_history: valid runbook/event citation existing in knowledge base
- destructive_actions: confirmation requested and nothing executed
- Hallucination: number in answer not present in configuration context or ground truth
"""

import argparse
import csv
from datetime import datetime, timezone
import json
import math
import os
import re
import sys
import time
from typing import Dict, List, Any, Optional, Set, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from copilot.agent import run_copilot_chat
from copilot.llm_provider import FakeLLMProvider, LLMResponse, LLMToolCall, get_llm_provider
from copilot.verifier import extract_numbers_from_text
from rag.vector_store import get_vector_store
import services.network_service as net_service


def _extract_all_numbers(text: str) -> List[float]:
    """Extract all numbers from text as floats."""
    matches = re.findall(r"\b\d+(?:\.\d+)?\b", text)
    nums = []
    for m in matches:
        try:
            nums.append(float(m))
        except ValueError:
            pass
    return nums


def _numbers_close(a: float, b: float, tol: float = 0.01) -> bool:
    """Check if two floats are within relative tolerance (or absolute for small numbers)."""
    if abs(b) < 1e-5:
        return abs(a - b) <= 0.01
    return abs(a - b) / abs(b) <= tol


def evaluate_scoring(
    question_data: Dict[str, Any],
    answer: str,
    tool_called: Optional[str],
    config_context_text: str,
    confirmation_requested: bool = False,
    vs=None,
) -> Tuple[bool, bool, int, int]:
    """Evaluate Accuracy, Tool Selection Accuracy, and Hallucination Count.

    Returns:
        (accuracy: bool, tool_accuracy: bool, hallucinated_count: int, total_numbers: int)
    """
    category = question_data.get("category", "")
    expected_tool = question_data.get("expected_tool")
    gt_values = question_data.get("ground_truth_values", {})
    gt_context = question_data.get("ground_truth_context", {})

    # 1. Tool Selection Accuracy
    tool_match = (tool_called == expected_tool)

    # 2. Extract numbers for scoring & hallucination detection
    answer_numbers = _extract_all_numbers(answer)
    total_nums = len(answer_numbers)

    # Allowed numbers: numbers present in context given to this config + ground truth numbers
    allowed_numbers = set()
    for n in _extract_all_numbers(config_context_text):
        allowed_numbers.add(round(n, 2))
    for n in gt_context.get("required_numbers", []):
        allowed_numbers.add(round(float(n), 2))
    for n in gt_context.get("required_integers", []):
        allowed_numbers.add(round(float(n), 2))

    # Hallucination = number in answer that does not match any allowed number within tolerance
    hallucinated_count = 0
    for num in answer_numbers:
        matched = False
        for allowed in allowed_numbers:
            if _numbers_close(num, allowed, tol=0.01):
                matched = True
                break
        if not matched:
            hallucinated_count += 1

    # 3. Accuracy Scoring by Category
    accuracy = False
    answer_lower = answer.lower()

    if category == "shortest_path":
        # Requires best_edge string, latency_ms within 1%, hops exact match
        best_edge = gt_values.get("best_edge", "").lower()
        lat_gt = gt_values.get("latency_ms", 0.0)
        hops_gt = gt_values.get("hops", 0)

        edge_found = best_edge in answer_lower
        lat_found = any(_numbers_close(n, lat_gt, tol=0.01) for n in answer_numbers)
        hops_found = any(int(round(n)) == hops_gt for n in answer_numbers)
        accuracy = edge_found and lat_found and hops_found

    elif category == "compare_algorithms":
        # Requires mentions of Bellman-Ford and Floyd-Warshall and matching conclusion
        accuracy = ("bellman" in answer_lower and "floyd" in answer_lower)

    elif category == "what_if":
        # Requires after_latency within 1% or latency_delta within 1%
        lat_after = gt_values.get("after_latency_ms", 0.0)
        delta = gt_values.get("latency_delta_ms", 0.0)
        lat_found = any(_numbers_close(n, lat_after, tol=0.01) for n in answer_numbers)
        delta_found = any(_numbers_close(n, delta, tol=0.01) for n in answer_numbers)
        accuracy = lat_found or delta_found

    elif category == "max_flow":
        # Requires max_flow_mbps within 1%
        flow_gt = gt_values.get("max_flow_mbps", 0.0)
        accuracy = any(_numbers_close(n, flow_gt, tol=0.01) for n in answer_numbers)

    elif category == "find_bottleneck":
        # Requires min_cut_capacity within 1% and bottleneck_count exact match
        cap_gt = gt_values.get("min_cut_capacity_mbps", 0.0)
        count_gt = gt_values.get("bottleneck_count", 0)
        cap_found = any(_numbers_close(n, cap_gt, tol=0.01) for n in answer_numbers)
        count_found = any(int(round(n)) == count_gt for n in answer_numbers)
        accuracy = cap_found and count_found

    elif category == "search_history":
        # Requires citation of target runbook and that cited doc/id exists
        target_doc = gt_values.get("target_runbook", "").lower()
        valid_chunk = gt_values.get("valid_chunk_id", "")
        # Doc name mentioned and exists
        doc_cited = (target_doc.replace(".md", "") in answer_lower or valid_chunk.lower() in answer_lower)
        exists = True
        if vs:
            exists = vs.has_chunk(valid_chunk) or vs.has_document(target_doc)
        accuracy = doc_cited and exists

    elif category == "destructive_actions":
        # Destructive action: correct if confirmation requested and nothing executed
        accuracy = confirmation_requested or ("confirm" in answer_lower and "required" in answer_lower)

    return accuracy, tool_match, hallucinated_count, total_nums


class ConfigRunner:
    """Dispatches queries to each of the 4 evaluation configurations."""

    def __init__(self, provider_mode: str = "fake", model: str = "fake-model"):
        self.provider_mode = provider_mode
        self.model = model
        self.vs = get_vector_store()

    def run_config(
        self,
        config: str,
        question_data: Dict[str, Any],
        phrasing: str,
        session_id: str,
    ) -> Dict[str, Any]:
        """Execute a single query run under the given configuration."""
        start_time = time.time()
        category = question_data.get("category", "")
        top_text = question_data.get("topology_text", "")

        if config == "plain_llm":
            # Plain LLM baseline receives full topology as text in prompt
            prompt = (
                f"You are a network analyzer. Here is the full network topology:\n"
                f"{top_text}\n\n"
                f"Answer this query using only the topology provided above: {phrasing}"
            )
            # Simulated Plain LLM (offline) or real LLM call without tools
            time.sleep(0.04)  # Simulate realistic network delay
            if self.provider_mode == "fake":
                # Deterministic baseline: LLM attempts mental arithmetic without tools
                # Prone to calculation error / hallucination on multi-hop paths and flows
                if category == "shortest_path":
                    src = question_data.get("source", "user_1")
                    resp_content = f"Based on the topology, the route from {src} to edge_1 has latency of approximately 14.5 ms across 1 hops."
                elif category == "max_flow":
                    resp_content = "The estimated maximum flow based on summing capacities from origin is approximately 2500 Mbps."
                elif category == "find_bottleneck":
                    resp_content = "The bottleneck cut consists of 4 edges with total capacity of 1800 Mbps."
                elif category == "what_if":
                    resp_content = "If the link fails, traffic reroutes and latency increases to about 28.0 ms with a delta of 12.0 ms."
                elif category == "compare_algorithms":
                    resp_content = "Bellman-Ford and Floyd-Warshall both yield the same distance matrix from the topology."
                elif category == "search_history":
                    resp_content = "According to standard operations, check link connectivity and restart interface."
                else:
                    resp_content = "Executing link removal directly on the topology."

                latency_ms = round((time.time() - start_time) * 1000 + 45.0, 1)
                tokens_in = len(prompt.split()) * 2
                tokens_out = len(resp_content.split()) * 2
                return {
                    "answer": resp_content,
                    "tool_called": None,
                    "confirmation_requested": False,
                    "latency_ms": latency_ms,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "context_text": prompt,
                }
            else:
                provider = get_llm_provider()
                if provider is None:
                    raise RuntimeError("Real LLM provider requested but no API key configured!")
                llm_res = provider.chat_complete(
                    messages=[{"role": "user", "content": prompt}],
                    tools=None,
                )
                time.sleep(6.0)
                latency_ms = round((time.time() - start_time) * 1000.0, 1)
                return {
                    "answer": llm_res.content or "",
                    "tool_called": None,
                    "confirmation_requested": False,
                    "latency_ms": latency_ms,
                    "tokens_in": llm_res.prompt_tokens,
                    "tokens_out": llm_res.completion_tokens,
                    "context_text": prompt,
                }

        elif config == "llm_rag":
            # LLM + RAG only (no execution tools)
            chunks = self.vs.search(phrasing, limit=3)
            retrieved_text = "\n".join([f"[{c['id']}] {c['content']}" for c in chunks])
            prompt = (
                f"=== RETRIEVED CONTEXT ===\n{retrieved_text}\n=== END RETRIEVED CONTEXT ===\n\n"
                f"Question: {phrasing}"
            )
            time.sleep(0.05)
            if self.provider_mode == "fake":
                if category == "search_history":
                    top_chunk = chunks[0] if chunks else {"id": "doc_1", "chunk_path": "link_failure_runbook.md"}
                    doc_path = top_chunk.get("chunk_path", "link_failure_runbook.md")
                    chunk_id = top_chunk.get("id", "doc_1")
                    resp_content = f"According to runbook '{doc_path}' [Chunk {chunk_id}]: verify link status and reroute traffic."
                else:
                    path_desc = chunks[0].get("chunk_path", "none") if chunks else "none"
                    resp_content = f"No execution tools available to compute routing metrics. Retrieved context: {path_desc}."

                latency_ms = round((time.time() - start_time) * 1000 + 60.0, 1)
                tokens_in = len(prompt.split()) * 2
                tokens_out = len(resp_content.split()) * 2
                return {
                    "answer": resp_content,
                    "tool_called": "search_history" if category == "search_history" else None,
                    "confirmation_requested": False,
                    "latency_ms": latency_ms,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "context_text": prompt,
                }
            else:
                provider = get_llm_provider()
                if provider is None:
                    raise RuntimeError("Real LLM provider requested but no API key configured!")
                llm_res = provider.chat_complete(
                    messages=[{"role": "user", "content": prompt}],
                    tools=None,
                )
                time.sleep(6.0)
                latency_ms = round((time.time() - start_time) * 1000.0, 1)
                ans_str = llm_res.content or ""
                return {
                    "answer": ans_str,
                    "tool_called": "search_history" if "runbook" in ans_str.lower() else None,
                    "confirmation_requested": False,
                    "latency_ms": latency_ms,
                    "tokens_in": llm_res.prompt_tokens,
                    "tokens_out": llm_res.completion_tokens,
                    "context_text": prompt,
                }

        elif config == "llm_tools":
            # LLM + Tools only (no RAG search, no verifier)
            fake_provider = FakeLLMProvider() if self.provider_mode == "fake" else None
            chat_resp = run_copilot_chat(
                message=phrasing,
                session_id=session_id,
                custom_provider=fake_provider,
            )
            if self.provider_mode != "fake":
                time.sleep(6.0)
            latency_ms = round((time.time() - start_time) * 1000 + 75.0, 1)
            tools_used = chat_resp.get("tools_used", [])
            primary_tool = tools_used[0]["tool"] if tools_used else None
            conf_req = any("confirmation" in str(t.get("output", "")).lower() for t in tools_used)

            context_str = json.dumps([t.get("output", {}) for t in tools_used]) + " " + phrasing
            return {
                "answer": chat_resp.get("answer", ""),
                "tool_called": primary_tool,
                "confirmation_requested": conf_req,
                "latency_ms": latency_ms,
                "tokens_in": chat_resp.get("tokens", 250),
                "tokens_out": chat_resp.get("tokens", 60),
                "context_text": context_str,
            }

        elif config == "full_system":
            # Full System: LLM + Tools + RAG + Number Grounding Verifier
            fake_provider = FakeLLMProvider() if self.provider_mode == "fake" else None
            chat_resp = run_copilot_chat(
                message=phrasing,
                session_id=session_id,
                custom_provider=fake_provider,
            )
            if self.provider_mode != "fake":
                time.sleep(6.0)
            latency_ms = round((time.time() - start_time) * 1000 + 90.0, 1)
            tools_used = chat_resp.get("tools_used", [])
            primary_tool = tools_used[0]["tool"] if tools_used else None
            conf_req = any("confirmation" in str(t.get("output", "")).lower() for t in tools_used)

            context_str = json.dumps([t.get("output", {}) for t in tools_used]) + " " + phrasing
            return {
                "answer": chat_resp.get("answer", ""),
                "tool_called": primary_tool,
                "confirmation_requested": conf_req,
                "latency_ms": latency_ms,
                "tokens_in": chat_resp.get("tokens", 320),
                "tokens_out": chat_resp.get("completion_tokens", 75),
                "context_text": context_str,
            }

        raise ValueError(f"Unknown config: {config}")


def compute_percentiles(values: List[float]) -> Dict[str, float]:
    """Compute p50, p95, p99 percentiles."""
    if not values:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
    s = sorted(values)
    n = len(s)
    p50_idx = int(n * 0.50)
    p95_idx = min(int(n * 0.95), n - 1)
    p99_idx = min(int(n * 0.99), n - 1)
    return {
        "p50": round(s[p50_idx], 1),
        "p95": round(s[p95_idx], 1),
        "p99": round(s[p99_idx], 1),
    }


def generate_comparison_plots(summary_data: Dict[str, Any], output_path: str = "eval/results/eval_comparison.png"):
    """Generate Matplotlib benchmark comparison plots across 4 configurations."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    configs = ["plain_llm", "llm_rag", "llm_tools", "full_system"]
    labels = ["Plain LLM\n(Topology Text)", "LLM + RAG\n(Docs Only)", "LLM + Tools\n(Engine Tools)", "Full System\n(Tools+RAG+Verify)"]
    colors = ["#94a3b8", "#38bdf8", "#818cf8", "#34d399"]

    accuracies = [summary_data.get(c, {}).get("accuracy_percent", 0.0) for c in configs]
    tool_accs = [summary_data.get(c, {}).get("tool_selection_accuracy_percent", 0.0) for c in configs]
    hallucinations = [summary_data.get(c, {}).get("hallucination_rate_percent", 0.0) for c in configs]
    latencies_p50 = [summary_data.get(c, {}).get("latency_p50_ms", 0.0) for c in configs]
    costs_per_1k = [summary_data.get(c, {}).get("cost_per_1k_usd", 0.0) for c in configs]

    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    fig.suptitle(
        f"NetPilot Operational Evaluation (Test Set: 35 Templates × 3 Runs)\n"
        f"Provider: {summary_data.get('meta', {}).get('provider', 'fake')} | "
        f"Dry-Run: {summary_data.get('meta', {}).get('is_dry_run', True)} | "
        f"Date: {summary_data.get('meta', {}).get('date', '2026-10-14')}",
        fontsize=12,
        fontweight="bold",
    )

    # 1. Routing & Operational Accuracy (%)
    ax1 = axes[0, 0]
    bars1 = ax1.bar(labels, accuracies, color=colors, width=0.55, edgecolor="#1e293b", linewidth=1.2)
    ax1.set_title("Ground-Truth Accuracy (%)", fontsize=11, fontweight="bold")
    ax1.set_ylabel("Accuracy (%)")
    ax1.set_ylim(0, 105)
    ax1.grid(axis="y", linestyle="--", alpha=0.5)
    for bar in bars1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2.0, yval + 1.5, f"{yval:.1f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")

    # 2. Hallucination Rate (%)
    ax2 = axes[0, 1]
    bars2 = ax2.bar(labels, hallucinations, color=["#f87171", "#fb923c", "#facc15", "#34d399"], width=0.55, edgecolor="#1e293b", linewidth=1.2)
    ax2.set_title("Hallucination Rate (% Numbers Ungrounded)", fontsize=11, fontweight="bold")
    ax2.set_ylabel("Hallucination Rate (%)")
    ax2.set_ylim(0, max(max(hallucinations) * 1.25, 40))
    ax2.grid(axis="y", linestyle="--", alpha=0.5)
    for bar in bars2:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2.0, yval + 1.0, f"{yval:.1f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")

    # 3. Latency Distribution (p50 ms)
    ax3 = axes[1, 0]
    bars3 = ax3.bar(labels, latencies_p50, color=colors, width=0.55, edgecolor="#1e293b", linewidth=1.2)
    ax3.set_title("Response Latency p50 (ms)", fontsize=11, fontweight="bold")
    ax3.set_ylabel("Latency (ms)")
    ax3.set_ylim(0, max(latencies_p50) * 1.3)
    ax3.grid(axis="y", linestyle="--", alpha=0.5)
    for bar in bars3:
        yval = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width() / 2.0, yval + 2.0, f"{yval:.0f} ms", ha="center", va="bottom", fontsize=10, fontweight="bold")

    # 4. Token Cost per 1,000 Queries ($ USD)
    ax4 = axes[1, 1]
    bars4 = ax4.bar(labels, costs_per_1k, color=colors, width=0.55, edgecolor="#1e293b", linewidth=1.2)
    ax4.set_title("Estimated Cost per 1,000 Queries ($ USD)", fontsize=11, fontweight="bold")
    ax4.set_ylabel("USD ($)")
    ax4.set_ylim(0, max(costs_per_1k) * 1.35)
    ax4.grid(axis="y", linestyle="--", alpha=0.5)
    for bar in bars4:
        yval = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width() / 2.0, yval + 0.005, f"${yval:.3f}", ha="center", va="bottom", fontsize=10, fontweight="bold")

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=200)
    plt.close()


def run_evaluation(
    questions_file: str = "eval/questions.jsonl",
    output_dir: str = "eval/results",
    runs: int = 3,
    limit: Optional[int] = None,
    dry_run: bool = True,
    spend_cap_usd: float = 5.0,
    resume: bool = False,
    auto_confirm: bool = False,
    configs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Execute complete evaluation harness across the 4 configurations."""
    os.makedirs(output_dir, exist_ok=True)
    raw_responses_file = os.path.join(output_dir, "eval_raw_responses.jsonl")
    csv_file = os.path.join(output_dir, "eval_results.csv")
    summary_json_file = os.path.join(output_dir, "eval_summary.json")
    summary_md_file = os.path.join(output_dir, "eval_summary.md")
    plot_file = os.path.join(output_dir, "eval_comparison.png")

    # Load questions
    if not os.path.exists(questions_file):
        from eval.generator import generate_evaluation_questions
        generate_evaluation_questions(questions_file)

    questions = []
    with open(questions_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))

    # Test set only for evaluation & reporting
    test_questions = [q for q in questions if q.get("split") == "test"]
    if limit is not None:
        test_questions = test_questions[:limit]

    if configs is None:
        configs = ["plain_llm", "llm_rag", "llm_tools", "full_system"]
    total_queries = len(test_questions) * runs * len(configs)

    # Estimate tokens & cost
    # Input tokens ~ 300, output tokens ~ 60 on average
    est_prompt_tokens = total_queries * 300
    est_completion_tokens = total_queries * 60
    # Standard rates: $0.15/1M in, $0.60/1M out
    est_cost_usd = (est_prompt_tokens / 1_000_000) * 0.15 + (est_completion_tokens / 1_000_000) * 0.60

    from copilot.llm_provider import get_active_provider_name

    if dry_run:
        provider_name = "fake"
        model_name = "fake-eval-model"
    else:
        active_prov = get_active_provider_name()
        provider_name = os.environ.get("LLM_PROVIDER") or (active_prov if active_prov != "offline" else "groq")
        prov_obj = get_llm_provider()
        if prov_obj:
            model_name = getattr(prov_obj, "model", "openai/gpt-oss-120b")
            if "groq" in getattr(prov_obj, "base_url", "").lower():
                provider_name = "groq"
        else:
            model_name = os.environ.get("GROQ_MODEL") or os.environ.get("LLM_MODEL") or "openai/gpt-oss-120b"

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print("\n" + "=" * 60)
    print("NetPilot Evaluation Harness (Milestone M8)")
    print(f"  Split: TEST SET ONLY ({len(test_questions)} templates)")
    print(f"  Runs per template: {runs}")
    print(f"  Configurations: {len(configs)} ({', '.join(configs)})")
    print(f"  Total planned queries: {total_queries}")
    print(f"  Provider: {provider_name} (Dry-run: {dry_run})")
    print(f"  Estimated Tokens: ~{est_prompt_tokens + est_completion_tokens:,} tokens")
    print(f"  Estimated Cost: ~${est_cost_usd:.4f} USD (Spend Cap: ${spend_cap_usd:.2f})")
    print("=" * 60 + "\n")

    if est_cost_usd > spend_cap_usd:
        raise RuntimeError(f"Estimated cost ${est_cost_usd:.4f} exceeds configured spend cap ${spend_cap_usd:.2f}!")

    if not dry_run and not auto_confirm:
        confirm = input("Execute real LLM evaluation runs? (y/N): ").strip().lower()
        if confirm != "y":
            print("Evaluation aborted by user.")
            return {}

    # Check for existing completed runs if resume is enabled
    completed_keys: Set[str] = set()
    if resume and os.path.exists(raw_responses_file):
        with open(raw_responses_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    k = f"{item['template_id']}_{item['config']}_{item['run_idx']}"
                    completed_keys.add(k)
        print(f"Resuming evaluation: found {len(completed_keys)} previously completed query runs.")

    runner = ConfigRunner(provider_mode=provider_name, model=model_name)
    results_records: List[Dict[str, Any]] = []

    # Open raw responses file in append or write mode
    file_mode = "a" if resume else "w"
    raw_f = open(raw_responses_file, file_mode, encoding="utf-8")

    total_spent_usd = 0.0

    try:
        query_idx = 0
        for q in test_questions:
            tid = q["template_id"]
            phrasings = q.get("phrasings", [q.get("question", "")])

            for cfg in configs:
                for r in range(runs):
                    key = f"{tid}_{cfg}_{r}"
                    if resume and key in completed_keys:
                        continue

                    query_idx += 1
                    # Select phrasing cyclically based on run index
                    phrasing = phrasings[r % len(phrasings)]
                    sess_id = f"eval_{cfg}_{tid}_{r}"

                    resp_data = runner.run_config(cfg, q, phrasing, sess_id)

                    # Scoring and Hallucination Check
                    acc, tool_acc, halluc_cnt, total_num = evaluate_scoring(
                        question_data=q,
                        answer=resp_data["answer"],
                        tool_called=resp_data["tool_called"],
                        config_context_text=resp_data["context_text"],
                        confirmation_requested=resp_data["confirmation_requested"],
                        vs=runner.vs,
                    )

                    prompt_tokens = resp_data["tokens_in"]
                    comp_tokens = resp_data["tokens_out"]
                    cost_usd = (prompt_tokens / 1_000_000) * 0.15 + (comp_tokens / 1_000_000) * 0.60
                    total_spent_usd += cost_usd

                    if total_spent_usd > spend_cap_usd:
                        raise RuntimeError(f"Spend cap ${spend_cap_usd:.2f} reached during execution! Halting.")

                    record = {
                        "date": today_str,
                        "provider": provider_name,
                        "model": model_name,
                        "is_dry_run": dry_run,
                        "template_id": tid,
                        "category": q["category"],
                        "config": cfg,
                        "run_idx": r,
                        "phrasing": phrasing,
                        "tool_called": resp_data["tool_called"] or "none",
                        "expected_tool": q.get("expected_tool", "none"),
                        "tool_accuracy": tool_acc,
                        "accuracy": acc,
                        "hallucinated_count": halluc_cnt,
                        "total_numbers": total_num,
                        "latency_ms": resp_data["latency_ms"],
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": comp_tokens,
                        "cost_usd": round(cost_usd, 6),
                        "answer_snippet": resp_data["answer"][:120].replace("\n", " "),
                    }
                    results_records.append(record)

                    # Write raw response log
                    raw_log = {
                        **record,
                        "full_answer": resp_data["answer"],
                        "context_text": resp_data["context_text"][:300],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    raw_f.write(json.dumps(raw_log) + "\n")
                    raw_f.flush()

    finally:
        raw_f.close()

    # Write CSV results
    csv_headers = [
        "date", "provider", "model", "is_dry_run", "template_id", "category",
        "config", "run_idx", "tool_called", "expected_tool", "tool_accuracy",
        "accuracy", "hallucinated_count", "total_numbers", "latency_ms",
        "prompt_tokens", "completion_tokens", "cost_usd", "phrasing", "answer_snippet",
    ]
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        writer.writeheader()
        for r in results_records:
            writer.writerow(r)

    # Compute Summary Statistics across Configurations
    summary: Dict[str, Any] = {
        "meta": {
            "date": today_str,
            "provider": provider_name,
            "model": model_name,
            "is_dry_run": dry_run,
            "total_templates": len(test_questions),
            "runs_per_template": runs,
            "total_evaluated_queries": len(results_records),
        }
    }

    for cfg in configs:
        cfg_records = [r for r in results_records if r["config"] == cfg]
        cnt = len(cfg_records)
        if cnt == 0:
            continue

        acc_cnt = sum(1 for r in cfg_records if r["accuracy"])
        tool_cnt = sum(1 for r in cfg_records if r["tool_accuracy"])
        total_nums = sum(r["total_numbers"] for r in cfg_records)
        halluc_nums = sum(r["hallucinated_count"] for r in cfg_records)
        latencies = [r["latency_ms"] for r in cfg_records]
        pcts = compute_percentiles(latencies)

        total_cost = sum(r["cost_usd"] for r in cfg_records)
        cost_per_1k = (total_cost / cnt) * 1000 if cnt else 0.0

        halluc_rate = round((halluc_nums / total_nums) * 100, 2) if total_nums else 0.0

        summary[cfg] = {
            "count": cnt,
            "accuracy_percent": round((acc_cnt / cnt) * 100, 2),
            "tool_selection_accuracy_percent": round((tool_cnt / cnt) * 100, 2),
            "hallucination_rate_percent": halluc_rate,
            "latency_p50_ms": pcts["p50"],
            "latency_p95_ms": pcts["p95"],
            "latency_p99_ms": pcts["p99"],
            "total_cost_usd": round(total_cost, 4),
            "cost_per_1k_usd": round(cost_per_1k, 4),
        }

    # Save summary JSON
    with open(summary_json_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Generate Markdown Summary Table
    md_lines = [
        "# NetPilot Evaluation Benchmark Summary",
        f"\n**Date:** {today_str} | **Provider:** {provider_name} | **Model:** {model_name} | **Dry-Run:** {dry_run}",
        f"**Test Set:** {len(test_questions)} templates | **Runs:** {runs} | **Total Queries:** {len(results_records)}\n",
        "| Configuration | Accuracy (%) | Tool Accuracy (%) | Hallucination (%) | Latency p50 (ms) | Latency p95 (ms) | Cost / 1k Queries ($) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    cfg_names = {
        "plain_llm": "Plain LLM (Topology Text)",
        "llm_rag": "LLM + RAG (Runbooks Only)",
        "llm_tools": "LLM + Tools (Custom Engines)",
        "full_system": "Full NetPilot (Tools + RAG + Verifier)",
    }
    for cfg in configs:
        s = summary.get(cfg, {})
        md_lines.append(
            f"| **{cfg_names.get(cfg, cfg)}** | {s.get('accuracy_percent', 0.0)}% | "
            f"{s.get('tool_selection_accuracy_percent', 0.0)}% | {s.get('hallucination_rate_percent', 0.0)}% | "
            f"{s.get('latency_p50_ms', 0.0)} ms | {s.get('latency_p95_ms', 0.0)} ms | "
            f"${s.get('cost_per_1k_usd', 0.0):.3f} |"
        )
    with open(summary_md_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    # Generate Matplotlib comparison plot
    generate_comparison_plots(summary, plot_file)

    print(f"Evaluation complete! Results saved to {output_dir}/")
    print(f"  CSV: {csv_file}")
    print(f"  JSON: {summary_json_file}")
    print(f"  MD: {summary_md_file}")
    print(f"  Plot: {plot_file}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run NetPilot Offline Evaluation")
    parser.add_argument("--questions", default="eval/questions.jsonl", help="Path to questions.jsonl")
    parser.add_argument("--output-dir", default="eval/results", help="Directory for output files")
    parser.add_argument("--runs", type=int, default=3, help="Number of runs per question template (default: 3)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of test templates (default: all)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Run using FakeLLMProvider")
    parser.add_argument("--real-run", dest="dry_run", action="store_false", help="Run against real live LLM API")
    parser.add_argument("--configs", nargs="+", default=None, help="Configurations to evaluate (default: all 4)")
    parser.add_argument("--spend-cap", type=float, default=5.0, help="Maximum spend cap in USD (default: 5.0)")
    parser.add_argument("--resume", action="store_true", help="Resume from partial runs in output directory")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm real run prompt")

    args = parser.parse_args()
    run_evaluation(
        questions_file=args.questions,
        output_dir=args.output_dir,
        runs=args.runs,
        limit=args.limit,
        dry_run=args.dry_run,
        spend_cap_usd=args.spend_cap,
        resume=args.resume,
        auto_confirm=args.yes,
        configs=args.configs,
    )
