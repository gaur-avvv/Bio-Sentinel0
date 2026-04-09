from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any

import httpx

from src.data.syndromic_schema import SyndromicRecord


class SupabaseStoreError(RuntimeError):
    """Raised when Supabase storage operations fail."""


class SupabaseSurveillanceStore:
    """Supabase-backed persistence for records and alerts via PostgREST."""

    def __init__(
        self,
        url: str | None,
        service_key: str | None,
        records_table: str = "encounters",
        alerts_table: str = "alerts",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.url = (url or "").rstrip("/")
        self.service_key = service_key or ""
        self.records_table = records_table
        self.alerts_table = alerts_table
        self.timeout_seconds = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.service_key)

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
        }

    def _base_rest_url(self, table: str) -> str:
        return f"{self.url}/rest/v1/{table}"

    def _request(
        self,
        method: str,
        table: str,
        *,
        params: dict[str, Any] | None = None,
        json_payload: Any = None,
        prefer: str | None = None,
    ) -> Any:
        if not self.enabled:
            raise SupabaseStoreError("Supabase is not configured. Set SUPABASE_URL and SUPABASE_KEY.")

        headers = self._headers()
        if prefer:
            headers["Prefer"] = prefer

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.request(
                    method=method,
                    url=self._base_rest_url(table),
                    params=params,
                    json=json_payload,
                    headers=headers,
                )
            response.raise_for_status()
            if not response.text:
                return None
            return response.json()
        except httpx.HTTPError as exc:
            raise SupabaseStoreError(f"Supabase request failed: {exc}") from exc

    def _serialize_record(self, record: SyndromicRecord, record_id: str | None = None) -> tuple[str, dict[str, Any]]:
        payload = record.model_dump(mode="json")
        rid = record_id or str(payload.get("record_id") or f"rec_{uuid.uuid4().hex[:12]}")
        payload["record_id"] = rid
        row = {
            "id": rid,
            "timestamp": record.timestamp.isoformat(),
            "patient_id": record.patient_id,
            "syndrome_category": record.syndrome_category,
            "severity": record.severity,
            "onset_days": record.onset_days,
            "age_group": record.age_group,
            "state": record.location.state,
            "district": record.location.district,
            "record_json": payload,
            "created_ts": datetime.now(timezone.utc).timestamp(),
        }
        return rid, row

    def save_record(self, record: SyndromicRecord) -> str:
        record_id, row = self._serialize_record(record)
        self._request(
            "POST",
            self.records_table,
            json_payload=[row],
            prefer="resolution=merge-duplicates,return=representation",
        )
        return record_id

    def save_record_payload(self, record: dict[str, Any]) -> str:
        record_id = str(record.get("record_id") or f"rec_{uuid.uuid4().hex[:12]}")
        record["record_id"] = record_id
        location = record.get("location", {})
        row = {
            "id": record_id,
            "timestamp": record.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "patient_id": record.get("patient_id", "anon-local"),
            "syndrome_category": record.get("syndrome_category", "acute_febrile_illness"),
            "severity": record.get("severity", "moderate"),
            "onset_days": int(record.get("onset_days", 0)),
            "age_group": record.get("age_group", "adult"),
            "state": location.get("state", "unknown"),
            "district": location.get("district", "unknown"),
            "record_json": record,
            "created_ts": datetime.now(timezone.utc).timestamp(),
        }
        self._request(
            "POST",
            self.records_table,
            json_payload=[row],
            prefer="resolution=merge-duplicates,return=representation",
        )
        return record_id

    def save_alert(self, alert: dict[str, Any], source: str, linked_record_id: str | None = None) -> str:
        alert_id = str(alert.get("alert_id") or f"alert_{uuid.uuid4().hex[:10]}")
        row = {
            "alert_id": alert_id,
            "severity": str(alert.get("severity", "monitor")),
            "score": float(alert.get("score", 0.0)),
            "message": str(alert.get("message", "")),
            "evidence_json": alert.get("evidence", {}),
            "source": source,
            "linked_record_id": linked_record_id,
            "created_ts": datetime.now(timezone.utc).timestamp(),
        }
        self._request(
            "POST",
            self.alerts_table,
            json_payload=[row],
            prefer="resolution=merge-duplicates,return=representation",
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
        params: dict[str, Any] = {
            "select": "record_json,id,syndrome_category,state,district,created_ts",
            "order": "created_ts.desc",
            "limit": max(1, min(limit, 200)),
            "offset": max(0, offset),
        }
        if state:
            params["state"] = f"eq.{state}"
        if district:
            params["district"] = f"eq.{district}"
        if syndrome:
            params["syndrome_category"] = f"eq.{syndrome}"

        rows = self._request("GET", self.records_table, params=params) or []
        output: list[dict[str, Any]] = []
        for row in rows:
            record_json = row.get("record_json")
            if isinstance(record_json, dict):
                output.append(record_json)
            else:
                output.append(
                    {
                        "record_id": row.get("id"),
                        "syndrome_category": row.get("syndrome_category"),
                        "location": {
                            "state": row.get("state"),
                            "district": row.get("district"),
                        },
                        "created_ts": row.get("created_ts"),
                    }
                )
        return output

    def get_record(self, record_id: str) -> dict[str, Any] | None:
        params = {
            "select": "record_json,id,syndrome_category,state,district,created_ts",
            "id": f"eq.{record_id}",
            "limit": 1,
        }
        rows = self._request("GET", self.records_table, params=params) or []
        if not rows:
            return None
        row = rows[0]
        if isinstance(row.get("record_json"), dict):
            return row["record_json"]
        return {
            "record_id": row.get("id"),
            "syndrome_category": row.get("syndrome_category"),
            "location": {
                "state": row.get("state"),
                "district": row.get("district"),
            },
            "created_ts": row.get("created_ts"),
        }

    def list_alerts(self, limit: int = 50, offset: int = 0, severity: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "select": "alert_id,severity,score,message,evidence_json,source,linked_record_id,created_ts",
            "order": "created_ts.desc",
            "limit": max(1, min(limit, 200)),
            "offset": max(0, offset),
        }
        if severity:
            params["severity"] = f"eq.{severity}"

        rows = self._request("GET", self.alerts_table, params=params) or []
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
        if not self.enabled:
            return {"enabled": False, "ok": False, "message": "Supabase is not configured"}

        try:
            _ = self._request("GET", self.records_table, params={"select": "id", "limit": 1})
            return {
                "enabled": True,
                "ok": True,
                "records_table": self.records_table,
                "alerts_table": self.alerts_table,
            }
        except SupabaseStoreError as exc:
            return {
                "enabled": True,
                "ok": False,
                "records_table": self.records_table,
                "alerts_table": self.alerts_table,
                "message": str(exc),
            }
