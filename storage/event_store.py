"""Structured SQLite Event Store for Mini CDN Simulator.

Logs every route computation, failure, reset, what-if, max-flow run, and topology upload
with structured metadata:
(id, timestamp, session_id, type, topology_name, inputs, before/after results, ops_count, compute_time_ms).
"""

import os
import sqlite3
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any


class NetworkEvent:
    """Represents a structured network event."""

    def __init__(
        self,
        event_id: str,
        timestamp: str,
        session_id: str,
        event_type: str,
        topology_name: str,
        inputs: Dict[str, Any],
        results: Dict[str, Any],
        ops_count: int = 0,
        compute_time_ms: float = 0.0,
    ):
        self.id = event_id
        self.timestamp = timestamp
        self.session_id = session_id
        self.type = event_type
        self.topology_name = topology_name
        self.inputs = inputs
        self.results = results
        self.ops_count = ops_count
        self.compute_time_ms = compute_time_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "type": self.type,
            "topology_name": self.topology_name,
            "inputs": self.inputs,
            "results": self.results,
            "ops_count": self.ops_count,
            "compute_time_ms": self.compute_time_ms,
        }


class EventStore:
    """SQLite-backed structured event store."""

    def __init__(self, db_path: str = "network_events.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    topology_name TEXT NOT NULL,
                    inputs TEXT NOT NULL,
                    results TEXT NOT NULL,
                    ops_count INTEGER NOT NULL,
                    compute_time_ms REAL NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);"
            )
            conn.commit()

    def log_event(
        self,
        event_type: str,
        session_id: str,
        topology_name: str,
        inputs: Dict[str, Any],
        results: Dict[str, Any],
        ops_count: int = 0,
        compute_time_ms: float = 0.0,
        event_id: Optional[str] = None,
    ) -> NetworkEvent:
        """Insert a new structured event into the SQLite event store."""
        eid = event_id or f"evt_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        event = NetworkEvent(
            event_id=eid,
            timestamp=timestamp,
            session_id=session_id,
            event_type=event_type,
            topology_name=topology_name,
            inputs=inputs,
            results=results,
            ops_count=ops_count,
            compute_time_ms=compute_time_ms,
        )

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO events (id, timestamp, session_id, type, topology_name, inputs, results, ops_count, compute_time_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    event.id,
                    event.timestamp,
                    event.session_id,
                    event.type,
                    event.topology_name,
                    json.dumps(event.inputs),
                    json.dumps(event.results),
                    event.ops_count,
                    event.compute_time_ms,
                ),
            )
            conn.commit()

        return event

    def get_event(self, event_id: str) -> Optional[NetworkEvent]:
        """Retrieve a single event by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM events WHERE id = ?;", (event_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_event(row)

    def list_events(
        self,
        session_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[NetworkEvent]:
        """Query recent events with optional session or event_type filtering."""
        query = "SELECT * FROM events WHERE 1=1"
        params: List[Any] = []

        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if event_type:
            query += " AND type = ?"
            params.append(event_type)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_event(r) for r in rows]

    def _row_to_event(self, row: sqlite3.Row) -> NetworkEvent:
        return NetworkEvent(
            event_id=row["id"],
            timestamp=row["timestamp"],
            session_id=row["session_id"],
            event_type=row["type"],
            topology_name=row["topology_name"],
            inputs=json.loads(row["inputs"]),
            results=json.loads(row["results"]),
            ops_count=row["ops_count"],
            compute_time_ms=row["compute_time_ms"],
        )


_GLOBAL_EVENT_STORE: Optional[EventStore] = None


def get_event_store(db_path: str = "network_events.db") -> EventStore:
    """Retrieve or initialize the global event store instance."""
    global _GLOBAL_EVENT_STORE
    if _GLOBAL_EVENT_STORE is None or _GLOBAL_EVENT_STORE.db_path != db_path:
        _GLOBAL_EVENT_STORE = EventStore(db_path=db_path)
    return _GLOBAL_EVENT_STORE
