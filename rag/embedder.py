"""Embedding provider: OpenAI-compatible API client and deterministic offline fake embedder."""

import os
import json
import math
import hashlib
import urllib.request
import urllib.error
from typing import List, Optional


class BaseEmbedder:
    """Base interface for embedding text."""
    def embed_text(self, text: str) -> List[float]:
        raise NotImplementedError


class DeterministicFakeEmbedder(BaseEmbedder):
    """Deterministic offline embedder for tests and offline mode.

    Creates unit-normalized vectors based on token hashing and domain keywords.
    Ensures semantically related queries (e.g. 'link failure' -> 'severed link')
    exhibit high cosine similarity deterministically.
    """
    def __init__(self, dimension: int = 64):
        self.dimension = dimension
        # Semantic keyword clusters mapped to target dimension buckets
        self.semantic_clusters = {
            "link": 0, "failure": 0, "severed": 0, "drop": 0, "cut": 0, "isolate": 0,
            "congestion": 8, "bottleneck": 8, "saturation": 8, "capacity": 8, "throttle": 8, "min-cut": 8,
            "outage": 16, "regional": 16, "failover": 16, "collapse": 16, "rehome": 16,
            "latency": 24, "regression": 24, "delay": 24, "spike": 24, "hops": 24, "suboptimal": 24,
            "topology": 32, "upload": 32, "rollback": 32, "corrupt": 32, "invalid": 32, "reset": 32,
            "bellman": 40, "floyd": 40, "route": 40, "path": 40, "flow": 48, "throughput": 48,
        }

    def embed_text(self, text: str) -> List[float]:
        vec = [0.0] * self.dimension
        words = [w.strip(".,;:!?\"'()[]{}").lower() for w in text.split()]

        if not words:
            vec[0] = 1.0
            return vec

        for w in words:
            if not w:
                continue
            # 1. Cluster weight if keyword matches
            if w in self.semantic_clusters:
                bucket = self.semantic_clusters[w]
                vec[bucket] += 3.0
                vec[(bucket + 1) % self.dimension] += 1.5

            # 2. General token hash projection
            h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            vec[idx] += 1.0

        # L2 normalization
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [round(x / norm, 6) for x in vec]
        else:
            vec[0] = 1.0
        return vec


class OpenAIEmbedder(BaseEmbedder):
    """Embeddings via standard OpenAI-compatible HTTP API."""
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def embed_text(self, text: str) -> List[float]:
        url = f"{self.base_url}/embeddings"
        payload = json.dumps({"input": text, "model": self.model}).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["data"][0]["embedding"]
        except Exception:
            # Fall back to deterministic embedder if remote call fails
            return DeterministicFakeEmbedder().embed_text(text)


def get_embedder(force_fake: bool = False) -> BaseEmbedder:
    """Retrieve active embedder based on environment or force fake."""
    if force_fake:
        return DeterministicFakeEmbedder()

    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        return DeterministicFakeEmbedder()

    base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").strip()
    model = os.environ.get("EMBED_MODEL", "text-embedding-3-small").strip()

    return OpenAIEmbedder(api_key=api_key, base_url=base_url, model=model)
