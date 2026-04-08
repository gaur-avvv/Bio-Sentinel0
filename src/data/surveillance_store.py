from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import uuid
from typing import Any

from src.data.syndromic_schema import SyndromicRecord


class SurveillanceStore:
    """SQLite-backed persistence for encounters and generated alerts."""

    def __init__(self, db_path: str = "data/surveillance.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS encounters (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    patient_id TEXT NOT NULL,
                    syndrome_category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    onset_days INTEGER NOT NULL,
                    age_group TEXT NOT NULL,
                    state TEXT NOT NULL,
                    district TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    created_ts REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id TEXT NOT NULL UNIQUE,
                    severity TEXT NOT NULL,
                    score REAL NOT NULL,
                    message TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    linked_record_id TEXT,
                    created_ts REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_encounters_state_district ON encounters(state, district)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_encounters_syndrome ON encounters(syndrome_category)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity)")

    def save_record(self, record: SyndromicRecord) -> str:
        payload = record.model_dump(mode="json")
        record_id = str(payload.get("record_id") or f"rec_{uuid.uuid4().hex[:12]}")
        payload["record_id"] = record_id
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO encounters (
                    id, timestamp, patient_id, syndrome_category, severity,
                    onset_days, age_group, state, district, record_json, created_ts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    record.timestamp.isoformat(),
                    record.patient_id,
                    record.syndrome_category,
                    record.severity,
                    record.onset_days,
                    record.age_group,
                    record.location.state,
                    record.location.district,
                    json.dumps(payload),
                    datetime.now(timezone.utc).timestamp(),
                ),
            )
        return record_id

    def save_alert(
        self,
        alert: dict[str, Any],
        source: str,
        linked_record_id: str | None = None,
    ) -> str:
        alert_id = str(alert.get("alert_id") or f"alert_{uuid.uuid4().hex[:10]}")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO alerts (
                    alert_id, severity, score, message, evidence_json,
                    source, linked_record_id, created_ts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert_id,
                    str(alert.get("severity", "monitor")),
                    float(alert.get("score", 0.0)),
                    str(alert.get("message", "")),
                    json.dumps(alert.get("evidence", {})),
                    source,
                    linked_record_id,
                    datetime.now(timezone.utc).timestamp(),
                ),
            )
        return alert_id

    def list_records(
        self,
        limit: int = 50,
        offset: int = 0,
        state: str | None = None,
        district: str | None = None,
        syndrome: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        if state:
            clauses.append("state = ?")
            params.append(state)
        if district:
            clauses.append("district = ?")
            params.append(district)
        if syndrome:
            clauses.append("syndrome_category = ?")
            params.append(syndrome)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT record_json
            FROM encounters
            {where_sql}
            ORDER BY created_ts DESC
            LIMIT ? OFFSET ?
        """
        params.extend([max(1, min(limit, 200)), max(0, offset)])

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [json.loads(row["record_json"]) for row in rows]

    def get_record(self, record_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT record_json FROM encounters WHERE id = ?",
                (record_id,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["record_json"])

    def list_alerts(self, limit: int = 50, offset: int = 0, severity: str | None = None) -> list[dict[str, Any]]:
        where_sql = "WHERE severity = ?" if severity else ""
        params: list[Any] = [severity] if severity else []
        params.extend([max(1, min(limit, 200)), max(0, offset)])

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT alert_id, severity, score, message, evidence_json, source, linked_record_id, created_ts
                FROM alerts
                {where_sql}
                ORDER BY created_ts DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()

        return [
            {
                "alert_id": row["alert_id"],
                "severity": row["severity"],
                "score": row["score"],
                "message": row["message"],
                "evidence": json.loads(row["evidence_json"]),
                "source": row["source"],
                "linked_record_id": row["linked_record_id"],
                "created_ts": row["created_ts"],
            }
            for row in rows
        ]

    def get_overview_stats(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc).timestamp()
        last_24h = now - (24 * 60 * 60)
        with self._connect() as conn:
            totals = conn.execute(
                """
                SELECT
                    COUNT(*) as total_records,
                    SUM(CASE WHEN created_ts >= ? THEN 1 ELSE 0 END) as records_last_24h
                FROM encounters
                """,
                (last_24h,),
            ).fetchone()
            alert_totals = conn.execute(
                "SELECT COUNT(*) as total_alerts FROM alerts"
            ).fetchone()
            syndrome_rows = conn.execute(
                """
                SELECT syndrome_category, COUNT(*) as count
                FROM encounters
                GROUP BY syndrome_category
                ORDER BY count DESC
                LIMIT 10
                """
            ).fetchall()

        return {
            "total_records": int(totals["total_records"] or 0),
            "records_last_24h": int(totals["records_last_24h"] or 0),
            "total_alerts": int(alert_totals["total_alerts"] or 0),
            "top_syndromes": {row["syndrome_category"]: int(row["count"]) for row in syndrome_rows},
        }