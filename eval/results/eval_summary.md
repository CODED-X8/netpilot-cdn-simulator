# NetPilot Evaluation Benchmark Summary

**Date:** 2026-10-20 | **Provider:** groq | **Model:** openai/gpt-oss-120b | **Dry-Run:** False
**Test Set:** 10 templates | **Runs:** 1 | **Total Queries:** 40

| Configuration | Accuracy (%) | Tool Accuracy (%) | Hallucination (%) | Latency p50 (ms) | Latency p95 (ms) | Cost / 1k Queries ($) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Plain LLM (Topology Text)** | 90.0% | 0.0% | 25.61% | 20867.6 ms | 34567.3 ms | $1.470 |
| **LLM + RAG (Runbooks Only)** | 20.0% | 0.0% | 43.88% | 14434.0 ms | 28672.6 ms | $0.716 |
| **LLM + Tools (Custom Engines)** | 100.0% | 70.0% | 34.17% | 23078.7 ms | 35772.7 ms | $3.441 |
| **Full NetPilot (Tools + RAG + Verifier)** | 90.0% | 60.0% | 30.77% | 21043.9 ms | 51612.5 ms | $0.676 |
