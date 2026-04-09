from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any

from src.data.syndromic_schema import SyndromicRecord


class RailwayStoreError(RuntimeError):
    """Raised when Railway Postgres operations fail."""


class RailwaySurveillanceStore:
    """Railway Postgres-backed persistence for records and alerts."""

    def __init__(
        self,
        database_url: str | None,
        records_table: str = "encounters",
        alerts_table: str = "alerts",
    ) -> None:
        self.database_url = database_url or ""
        self.records_table = records_table
        self.alerts_table = alerts_table

    def _require_psycopg(self) -> None:
        try:
            import psycopg  # noqa: F401
        except Exception as exc:
            raise RailwayStoreError("psycopg is not installed. Add psycopg[binary] to requirements.") from exc

    @property
    def enabled(self) -> bool:
        if not self.database_url:
            return False
        try:
            self._require_psycopg()
            return True
        except RailwayStoreError:
            return False

    def _connect(self):
        self._require_psycopg()
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(self.database_url, row_factory=dict_row)

    def _init_db(self) -> None:
        if not self.enabled:
            return

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self.records_table} (
                        id TEXT PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        patient_id TEXT NOT NULL,
                        syndrome_category TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        onset_days INTEGER NOT NULL,
                        age_group TEXT NOT NULL,
                        state TEXT NOT NULL,
                        district TEXT NOT NULL,
                        record_json JSONB NOT NULL,
                        created_ts DOUBLE PRECISION NOT NULL
                    )
                    """
                )
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self.alerts_table} (
                        id BIGSERIAL PRIMARY KEY,
                        alert_id TEXT NOT NULL UNIQUE,
                        severity TEXT NOT NULL,
                        score DOUBLE PRECISION NOT NULL,
                        message TEXT NOT NULL,
                        evidence_json JSONB NOT NULL,
                        source TEXT NOT NULL,
                        linked_record_id TEXT,
                        created_ts DOUBLE PRECISION NOT NULL
                    )
                    """
                )
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self.records_table}_state_district ON {self.records_table}(state, district)"
                )
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self.records_table}_syndrome ON {self.records_table}(syndrome_category)"
                )
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self.alerts_table}_severity ON {self.alerts_table}(severity)"
                )
            conn.commit()

    def _ensure_ready(self) -> None:
        if not self.database_url:
            raise RailwayStoreError("Railway DATABASE_URL is not configured")
        self._init_db()

    def save_record(self, record: SyndromicRecord) -> str:
        return self.save_record_payload(record.model_dump(mode="json"))

    def save_record_payload(self, record: dict[str, Any]) -> str:
        self._ensure_ready()
        from psycopg.types.json import Jsonb

        record_id = str(record.get("record_id") or f"rec_{uuid.uuid4().hex[:12]}")
        record["record_id"] = record_id
        location = record.get("location", {})

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self.records_table} (
                        id, timestamp, patient_id, syndrome_category, severity,
                        onset_days, age_group, state, district, record_json, created_ts
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        timestamp = EXCLUDED.timestamp,
                        patient_id = EXCLUDED.patient_id,
                        syndrome_category = EXCLUDED.syndrome_category,
                        severity = EXCLUDED.severity,
                        onset_days = EXCLUDED.onset_days,
                        age_group = EXCLUDED.age_group,
                        state = EXCLUDED.state,
                        district = EXCLUDED.district,
                        record_json = EXCLUDED.record_json,
                        created_ts = EXCLUDED.created_ts
                    """,
                    (
                        record_id,
                        record.get("timestamp", datetime.now(timezone.utc).isoformat()),
                        record.get("patient_id", "anon-local"),
                        record.get("syndrome_category", "acute_febrile_illness"),
                        record.get("severity", "moderate"),
                        int(record.get("onset_days", 0)),
                        record.get("age_group", "adult"),
                        location.get("state", "unknown"),
                        location.get("district", "unknown"),
                        Jsonb(record),
                        datetime.now(timezone.utc).timestamp(),
                    ),
                )
            conn.commit()

        return record_id

    def save_alert(self, alert: dict[str, Any], source: str, linked_record_id: str | None = None) -> str:
        self._ensure_ready()
        from psycopg.types.json import Jsonb

        alert_id = str(alert.get("alert_id") or f"alert_{uuid.uuid4().hex[:10]}")

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self.alerts_table} (
                        alert_id, severity, score, message, evidence_json,
                        source, linked_record_id, created_ts
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (alert_id) DO UPDATE SET
                        severity = EXCLUDED.severity,
                        score = EXCLUDED.score,
                        message = EXCLUDED.message,
                        evidence_json = EXCLUDED.evidence_json,
                        source = EXCLUDED.source,
                        linked_record_id = EXCLUDED.linked_record_id,
                        created_ts = EXCLUDED.created_ts
                    """,
                    (
                        alert_id,
                        str(alert.get("severity", "monitor")),
                        float(alert.get("score", 0.0)),
                        str(alert.get("message", "")),
                        Jsonb(alert.get("evidence", {})),
                        source,
                        linked_record_id,
                        datetime.now(timezone.utc).timestamp(),
                    ),
                )
            conn.commit()

        return alert_id

    def list_records(
        self,
        limit: int = 50,
        offset: int = 0,
        state: str | None = None,
        district: str | None = None,
        syndrome: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_ready()
        clauses: list[str] = []
        params: list[Any] = []

        if state:
            clauses.append("state = %s")
            params.append(state)
        if district:
            clauses.append("district = %s")
            params.append(district)
        if syndrome:
            clauses.append("syndrome_category = %s")
            params.append(syndrome)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([max(1, min(limit, 200)), max(0, offset)])

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT record_json
                    FROM {self.records_table}
                    {where_sql}
                    ORDER BY created_ts DESC
                    LIMIT %s OFFSET %s
                    """,
                    params,
                )
                rows = cur.fetchall()

        return [dict(row.get("record_json") or {}) for row in rows]

    def get_record(self, record_id: str) -> dict[str, Any] | None:
        self._ensure_ready()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT record_json FROM {self.records_table} WHERE id = %s LIMIT 1",
                    (record_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return dict(row.get("record_json") or {})

    def list_alerts(self, limit: int = 50, offset: int = 0, severity: str | None = None) -> list[dict[str, Any]]:
        self._ensure_ready()
        where_sql = "WHERE severity = %s" if severity else ""
        params: list[Any] = [severity] if severity else []
        params.extend([max(1, min(limit, 200)), max(0, offset)])

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT alert_id, severity, score, message, evidence_json, source, linked_record_id, created_ts
                    FROM {self.alerts_table}
                    {where_sql}
                    ORDER BY created_ts DESC
                    LIMIT %s OFFSET %s
                    """,
                    params,
                )
                rows = cur.fetchall()

        return [
            {
                "alert_id": row.get("alert_id"),
                "severity": row.get("severity"),
                "score": row.get("score"),
                "message": row.get("message"),
                "evidence": row.get("evidence_json") or {},
                "source": row.get("source"),
                "linked_record_id": row.get("linked_record_id"),
                "created_ts": row.get("created_ts"),
            }
            for row in rows
        ]

    def health(self) -> dict[str, Any]:
        if not self.database_url:
            return {"enabled": False, "ok": False, "message": "DATABASE_URL is not configured"}
        try:
            self._init_db()
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 as ok")
                    _ = cur.fetchone()
            return {
                "enabled": True,
                "ok": True,
                "records_table": self.records_table,
                "alerts_table": self.alerts_table,
            }
        except Exception as exc:
            return {
                "enabled": True,
                "ok": False,
                "records_table": self.records_table,
                "alerts_table": self.alerts_table,
                "message": str(exc),
            }