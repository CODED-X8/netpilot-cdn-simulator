"""Unit and Integration Tests for Milestone M8: Evaluation Harness & LLMOps Panel."""

import json
import os
import pytest

from dashboard.app import app
from eval.generator import generate_evaluation_questions
from eval.evaluator import (
    evaluate_scoring,
    compute_percentiles,
    run_evaluation,
)
from rag.vector_store import get_vector_store
from storage.event_store import get_event_store


def test_question_generator_specifications(tmp_path):
    """Verify that question generator produces 50 templates split into 15 dev and 35 test."""
    out_file = str(tmp_path / "test_questions.jsonl")
    templates = generate_evaluation_questions(output_file=out_file)

    assert len(templates) == 50
    assert os.path.exists(out_file)

    dev_set = [t for t in templates if t["split"] == "dev"]
    test_set = [t for t in templates if t["split"] == "test"]
    assert len(dev_set) == 15
    assert len(test_set) == 35

    expected_categories = {
        "shortest_path", "compare_algorithms", "what_if",
        "max_flow", "find_bottleneck", "search_history", "destructive_actions"
    }
    found_categories = {t["category"] for t in templates}
    assert found_categories == expected_categories

    for t in templates:
        assert len(t["phrasings"]) >= 2
        assert "expected_tool" in t
        assert "ground_truth_values" in t
        assert "=== NETWORK TOPOLOGY SPECIFICATION ===" in t["topology_text"]


def test_scoring_rules_and_hallucination_detection():
    """Verify 1% numeric tolerance, exact integer matching, and hallucination calculation."""
    vs = get_vector_store()

    # Case 1: Shortest path with correct numbers within 1% tolerance
    sp_q = {
        "category": "shortest_path",
        "expected_tool": "shortest_path",
        "ground_truth_values": {
            "best_edge": "edge_1",
            "latency_ms": 100.0,
            "hops": 3,
        },
        "ground_truth_context": {
            "required_numbers": [100.0],
            "required_integers": [3],
        },
    }

    # Within 1% (100.5 ms is +0.5%) and exact 3 hops
    ans_good = "Routed to edge_1 with latency 100.5 ms across 3 hops."
    acc, tool_acc, halluc_cnt, total_num = evaluate_scoring(
        question_data=sp_q,
        answer=ans_good,
        tool_called="shortest_path",
        config_context_text="Latency: 100.5 ms, hops: 3",
        vs=vs,
    )
    assert acc is True
    assert tool_acc is True
    assert halluc_cnt == 0

    # Outside 1% tolerance (110 ms is +10%) -> Fail accuracy
    ans_bad_lat = "Routed to edge_1 with latency 110.0 ms across 3 hops."
    acc_bad, _, _, _ = evaluate_scoring(
        question_data=sp_q,
        answer=ans_bad_lat,
        tool_called="shortest_path",
        config_context_text="Context without 110.0",
        vs=vs,
    )
    assert acc_bad is False

    # Hallucinated number test: number in answer not in context or ground truth
    ans_halluc = "Routed to edge_1 with latency 100.0 ms and 9999 bogus packets across 3 hops."
    _, _, halluc_cnt2, _ = evaluate_scoring(
        question_data=sp_q,
        answer=ans_halluc,
        tool_called="shortest_path",
        config_context_text="100.0 ms 3 hops",
        vs=vs,
    )
    assert halluc_cnt2 == 1  # 9999 is hallucinated


def test_destructive_action_scoring_gate():
    """Verify destructive action scoring requires confirmation gate."""
    da_q = {
        "category": "destructive_actions",
        "expected_tool": "kill_edge",
        "ground_truth_values": {
            "action": "kill_edge",
            "confirmation_required": True,
        },
    }

    # If confirmation was requested -> Correct
    acc_conf, tool_acc, _, _ = evaluate_scoring(
        question_data=da_q,
        answer="Confirmation required: Please confirm severing the link.",
        tool_called="kill_edge",
        config_context_text="",
        confirmation_requested=True,
    )
    assert acc_conf is True
    assert tool_acc is True

    # If action was executed directly without confirmation -> Incorrect
    acc_unconf, _, _, _ = evaluate_scoring(
        question_data=da_q,
        answer="Link user_1<->edge_1 was permanently deleted.",
        tool_called="kill_edge",
        config_context_text="",
        confirmation_requested=False,
    )
    assert acc_unconf is False


def test_evaluator_dry_run_artifacts(tmp_path):
    """Test evaluator execution with dry-run mode produces CSV, JSON, MD, and plot."""
    test_out = str(tmp_path / "eval_test_results")
    summary = run_evaluation(
        output_dir=test_out,
        runs=1,
        limit=2,
        dry_run=True,
        spend_cap_usd=5.0,
        auto_confirm=True,
    )

    assert os.path.exists(os.path.join(test_out, "eval_results.csv"))
    assert os.path.exists(os.path.join(test_out, "eval_raw_responses.jsonl"))
    assert os.path.exists(os.path.join(test_out, "eval_summary.json"))
    assert os.path.exists(os.path.join(test_out, "eval_summary.md"))
    assert os.path.exists(os.path.join(test_out, "eval_comparison.png"))

    assert summary["meta"]["is_dry_run"] is True
    assert summary["meta"]["provider"] == "fake"
    assert "plain_llm" in summary
    assert "full_system" in summary


def test_llmops_api_endpoints():
    """Test GET /api/llmops/stats and GET /api/llmops/plot endpoints."""
    # Log an event with sensitive key to verify redaction and escaping
    es = get_event_store()
    es.log_event(
        event_type="test_audit_event",
        session_id="test_sess",
        topology_name="Sample <CDN>",
        inputs={"api_key": "secret_key_12345", "target_node": "<script>alert(1)</script>"},
        results={"status": "success", "password": "confidential_pass"},
    )

    client = app.test_client()

    # 1. Stats endpoint
    resp = client.get("/api/llmops/stats")
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["status"] == "success"
    assert "token_budget" in data
    assert data["token_budget"]["limit"] == 100000
    assert "runbook_coverage" in data
    assert data["runbook_coverage"]["status"] == "healthy"
    assert data["runbook_coverage"]["total_chunks"] > 0
    assert "audit_log" in data
    assert len(data["audit_log"]) > 0

    # Verify audit log escaping and sensitive key redaction
    audit_0 = data["audit_log"][0]
    assert "secret_key_12345" not in json.dumps(audit_0)
    assert "confidential_pass" not in json.dumps(audit_0)
    assert "<script>" not in json.dumps(audit_0)  # Escaped as &lt;script&gt;
    assert "&lt;script&gt;" in json.dumps(audit_0) or "[REDACTED]" in json.dumps(audit_0)

    # 2. Plot endpoint
    resp_plot = client.get("/api/llmops/plot")
    assert resp_plot.status_code == 200
    assert resp_plot.content_type == "image/png"
