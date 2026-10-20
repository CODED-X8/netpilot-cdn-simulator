"""SQLite-backed Vector Store with pure Python cosine similarity (Milestone M5)."""

import os
import re
import json
import sqlite3
import math
from typing import List, Dict, Any, Optional

from .embedder import get_embedder, BaseEmbedder
from storage.event_store import get_event_store, get_default_db_path

RUNBOOKS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "runbooks"))


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine similarity between two numeric vectors in pure Python."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0

    return round(dot / (norm1 * norm2), 5)


class VectorStore:
    """Vector database backed by SQLite storing document embeddings."""

    def __init__(self, db_path: Optional[str] = None, embedder: Optional[BaseEmbedder] = None):
        self.db_path = db_path if db_path is not None else get_default_db_path()
        self.embedder = embedder or get_embedder()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create documents table if it doesn't already exist."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    doc_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    chunk_path TEXT NOT NULL,
                    embedding_json TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_type ON documents(doc_type)")
            conn.commit()

    def index_document(
        self,
        doc_id: str,
        doc_type: str,
        title: str,
        content: str,
        chunk_path: str,
        embedding: Optional[List[float]] = None,
    ) -> None:
        """Index a single chunk/document."""
        if embedding is None:
            text_to_embed = f"{title}\n{content}"
            embedding = self.embedder.embed_text(text_to_embed)

        emb_json = json.dumps(embedding)
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO documents (id, doc_type, title, content, chunk_path, embedding_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (doc_id, doc_type, title, content, chunk_path, emb_json),
            )
            conn.commit()

    def has_chunk(self, chunk_id: str) -> bool:
        """Check if a chunk id exists in the documents table."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT 1 FROM documents WHERE id = ?", (chunk_id,)).fetchone()
            return row is not None

    def has_document(self, filename: str) -> bool:
        """Check if any chunk belongs to the specified filename."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT 1 FROM documents WHERE chunk_path LIKE ?", (f"%{filename}%",)).fetchone()
            return row is not None

    def get_document_count(self) -> int:
        """Get total number of indexed document chunks."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()
            return int(row["cnt"]) if row else 0

    def search(
        self,
        query: str,
        doc_type: Optional[str] = None,
        limit: int = 3,
        min_score: float = 0.1,
    ) -> List[Dict[str, Any]]:
        """Search stored documents using pure Python cosine similarity."""
        query_vec = self.embedder.embed_text(query)

        query_sql = "SELECT id, doc_type, title, content, chunk_path, embedding_json FROM documents"
        params = []
        if doc_type:
            query_sql += " WHERE doc_type = ?"
            params.append(doc_type)

        results = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query_sql, params)
            rows = cursor.fetchall()

            for row in rows:
                try:
                    doc_vec = json.loads(row["embedding_json"])
                except Exception:
                    continue

                sim = cosine_similarity(query_vec, doc_vec)
                if sim >= min_score:
                    results.append({
                        "id": row["id"],
                        "doc_type": row["doc_type"],
                        "title": row["title"],
                        "content": row["content"],
                        "chunk_path": row["chunk_path"],
                        "similarity": sim,
                    })

        # Sort descending by similarity score
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    def index_runbooks(self, runbooks_dir: str = RUNBOOKS_DIR) -> int:
        """Parse all markdown runbooks, chunk them by heading, and index."""
        if not os.path.isdir(runbooks_dir):
            return 0

        indexed_count = 0
        for filename in sorted(os.listdir(runbooks_dir)):
            if not filename.endswith(".md"):
                continue

            file_path = os.path.join(runbooks_dir, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            chunks = self._chunk_markdown(filename, content)
            for chunk in chunks:
                self.index_document(
                    doc_id=chunk["id"],
                    doc_type="runbook",
                    title=chunk["title"],
                    content=chunk["content"],
                    chunk_path=chunk["chunk_path"],
                )
                indexed_count += 1

        return indexed_count

    def _chunk_markdown(self, filename: str, content: str) -> List[Dict[str, str]]:
        """Split markdown content by ## and ### headings."""
        lines = content.splitlines()
        chunks = []
        current_heading = filename
        current_lines: List[str] = []

        for line in lines:
            if line.startswith("## ") or line.startswith("### "):
                if current_lines:
                    body = "\n".join(current_lines).strip()
                    if body:
                        chunk_path = f"{filename}#{current_heading}"
                        slug = re.sub(r"[^a-zA-Z0-9_]", "_", chunk_path.lower())
                        chunks.append({
                            "id": slug,
                            "title": current_heading,
                            "content": body,
                            "chunk_path": chunk_path,
                        })
                current_heading = line.lstrip("#").strip()
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            body = "\n".join(current_lines).strip()
            if body:
                chunk_path = f"{filename}#{current_heading}"
                slug = re.sub(r"[^a-zA-Z0-9_]", "_", chunk_path.lower())
                chunks.append({
                    "id": slug,
                    "title": current_heading,
                    "content": body,
                    "chunk_path": chunk_path,
                })

        return chunks

    def sync_events(self, limit: int = 50) -> int:
        """Sync recent events from SQLite event store into vector store."""
        event_store = get_event_store(self.db_path)
        events = event_store.list_events(limit=limit)

        synced = 0
        for ev in events:
            ev_id = f"event_{ev.id}"
            title = f"Event #{ev.id}: {ev.type} ({ev.topology_name})"
            content = (
                f"Event ID: {ev.id}\n"
                f"Type: {ev.type}\n"
                f"Timestamp: {ev.timestamp}\n"
                f"Inputs: {json.dumps(ev.inputs)}\n"
                f"Results: {json.dumps(ev.results)}"
            )
            chunk_path = f"event_store#{ev.id}"
            self.index_document(
                doc_id=ev_id,
                doc_type="event",
                title=title,
                content=content,
                chunk_path=chunk_path,
            )
            synced += 1

        return synced


# Singleton accessor
_VECTOR_STORE: Optional[VectorStore] = None


def get_vector_store(db_path: Optional[str] = None, force_reinit: bool = False) -> VectorStore:
    """Retrieve singleton vector store instance and ensure runbooks are loaded."""
    global _VECTOR_STORE
    resolved_path = db_path if db_path is not None else get_default_db_path()
    if _VECTOR_STORE is None or force_reinit or _VECTOR_STORE.db_path != resolved_path:
        _VECTOR_STORE = VectorStore(db_path=resolved_path)
        # Ensure runbooks are indexed
        _VECTOR_STORE.index_runbooks()
    return _VECTOR_STORE
