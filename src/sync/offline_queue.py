from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import sqlite3
from typing import Any


class OfflineSyncQueue:
    """SQLite-backed queue with retry metadata for offline sync."""

    def __init__(self, db_path: str = "data/sync_queue.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS queue (
                    id TEXT PRIMARY KEY,
                    encounter_json TEXT NOT NULL,
                    sync_target TEXT NOT NULL,
                    priority INTEGER DEFAULT 1,
                    retry_count INTEGER DEFAULT 0,
                    next_retry_ts REAL NOT NULL,
                    created_ts REAL NOT NULL,
                    last_modified_ts REAL NOT NULL,
                    vector_clock TEXT,
                    resolved INTEGER DEFAULT 0,
                    resolution_log TEXT
                )
                """
            )

    def enqueue(self, encounter: dict[str, Any], target: str, priority: int = 1) -> str:
        now = datetime.now(timezone.utc).timestamp()
        queue_id = f"q_{int(now * 1000)}_{abs(hash(json.dumps(encounter, sort_keys=True))) % 100000}"
        vector_clock = json.dumps({os.getenv("DEVICE_ID", "unknown"): now})
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO queue (
                    id, encounter_json, sync_target, priority,
                    next_retry_ts, created_ts, last_modified_ts, vector_clock
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    queue_id,
                    json.dumps(encounter),
                    target,
                    priority,
                    now,
                    now,
                    now,
                    vector_clock,
                ),
            )
        return queue_id

    def get_due_items(self, limit: int = 10) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).timestamp()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM queue
                WHERE resolved = 0 AND next_retry_ts <= ?
                ORDER BY priority DESC, next_retry_ts ASC
                LIMIT ?
                """,
                (now, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_resolved(self, queue_id: str, server_response: dict[str, Any], vector_clock: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).timestamp()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE queue SET
                    resolved = 1,
                    last_modified_ts = ?,
                    resolution_log = ?,
                    vector_clock = ?
                WHERE id = ?
                """,
                (
                    now,
                    json.dumps({"server_response": server_response, "resolved_at": now}),
                    json.dumps(vector_clock),
                    queue_id,
                ),
            )

    def increment_retry(self, queue_id: str, error: str) -> None:
        now = datetime.utcnow().timestamp()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT retry_count, vector_clock FROM queue WHERE id = ?",
                (queue_id,),
            ).fetchone()
            if not row:
                return
            retry_count = int(row[0]) + 1
            vc = json.loads(row[1]) if row[1] else {}
            vc[os.getenv("DEVICE_ID", "unknown")] = now
            backoff = min(300 * (2 ** retry_count), 7200)
            conn.execute(
                """
                UPDATE queue SET
                    retry_count = ?,
                    next_retry_ts = ?,
                    last_modified_ts = ?,
                    vector_clock = ?,
                    resolution_log = ?
                WHERE id = ?
                """,
                (
                    retry_count,
                    now + backoff,
                    now,
                    json.dumps(vc),
                    json.dumps({"last_error": error, "retry": retry_count}),
                    queue_id,
                ),
            )

    def get_queue_stats(self) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN resolved = 0 THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN priority >= 3 AND resolved = 0 THEN 1 ELSE 0 END) as critical_pending,
                    AVG(retry_count) as avg_retries
                FROM queue
                """
            ).fetchone()
        return {
            "total_items": int(row[0] or 0),
            "pending_sync": int(row[1] or 0),
            "critical_pending": int(row[2] or 0),
            "avg_retry_count": round(float(row[3] or 0.0), 2),
        }
