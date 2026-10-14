# NetPilot Evaluation Benchmark Summary

**Date:** 2026-10-14 | **Provider:** fake | **Model:** fake-eval-model | **Dry-Run:** True
**Test Set:** 35 templates | **Runs:** 3 | **Total Queries:** 420

| Configuration | Accuracy (%) | Tool Accuracy (%) | Hallucination (%) | Latency p50 (ms) | Latency p95 (ms) | Cost / 1k Queries ($) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Plain LLM (Topology Text)** | 5.71% | 0.0% | 31.58% | 85.1 ms | 85.2 ms | $0.285 |
| **LLM + RAG (Runbooks Only)** | 13.33% | 17.14% | 0.0% | 115.9 ms | 117.5 ms | $0.059 |
| **LLM + Tools (Custom Engines)** | 61.9% | 71.43% | 0.0% | 89.8 ms | 287.2 ms | $0.073 |
| **Full NetPilot (Tools + RAG + Verifier)** | 61.9% | 71.43% | 0.0% | 100.8 ms | 303.3 ms | $0.093 |
