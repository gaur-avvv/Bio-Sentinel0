from __future__ import annotations

from datetime import datetime
from typing import Any
import os

import httpx

from src.sync.offline_queue import OfflineSyncQueue


class IDSPSyncTool:
    """Sync structured records to IDSP/IHIP style endpoint with offline queue fallback."""

    def __init__(self, queue_path: str = "data/sync_queue.db", api_base: str | None = None) -> None:
        self.queue = OfflineSyncQueue(db_path=queue_path)
        self.api_base = api_base or os.getenv("IDSP_API_BASE", "https://idsp.mohfw.gov.in/api")
        self.token = os.getenv("IDSP_API_TOKEN", "")

    def __call__(self, encounter: dict[str, Any], force_sync: bool = False) -> dict[str, Any]:
        if not self._is_online() and not force_sync:
            qid = self.queue.enqueue(encounter, target="idsp", priority=self._priority(encounter))
            return {"status": "queued", "queue_id": qid, "message": "offline queued"}

        payload = self._build_payload(encounter)
        try:
            response = httpx.post(
                f"{self.api_base}/v1/surveillance/report",
                json=payload,
                headers={"Authorization": f"Bearer {self.token}"} if self.token else {},
                timeout=15,
            )
            response.raise_for_status()
            report_id = response.json().get("report_id", f"IDSP-{int(datetime.utcnow().timestamp())}")
            return {"status": "success", "report_id": report_id}
        except Exception as exc:
            if not force_sync:
                qid = self.queue.enqueue(encounter, target="idsp", priority=self._priority(encounter))
                return {"status": "queued", "queue_id": qid, "error": str(exc)}
            return {"status": "failed", "error": str(exc)}

    def _priority(self, encounter: dict[str, Any]) -> int:
        if encounter.get("severity") in {"severe", "critical"}:
            return 3
        if encounter.get("severity") == "moderate":
            return 2
        return 1

    def _build_payload(self, encounter: dict[str, Any]) -> dict[str, Any]:
        return {
            "report_type": "S",
            "syndrome_code": encounter.get("syndrome") or encounter.get("syndrome_category"),
            "severity": encounter.get("severity", "moderate"),
            "location": {
                "state_code": encounter.get("state_code", "IN"),
                "district": encounter.get("district", "unknown"),
                "village": encounter.get("village"),
            },
            "clinical": {
                "icd10": encounter.get("icd10_codes", []),
                "symptoms": encounter.get("symptoms", []),
            },
            "metadata": {
                "source": "bio_sentinel",
                "confidence": encounter.get("confidence_score", 0.5),
            },
        }

    def _is_online(self) -> bool:
        try:
            response = httpx.get(f"{self.api_base}/health", timeout=4)
            return response.status_code < 500
        except Exception:
            return False

    def process_queue(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        due = self.queue.get_due_items(limit=20)
        for item in due:
            encounter = json_load(item["encounter_json"])
            result = self(encounter, force_sync=True)
            if result.get("status") == "success":
                self.queue.mark_resolved(
                    queue_id=item["id"],
                    server_response=result,
                    vector_clock={"server": datetime.utcnow().timestamp()},
                )
            else:
                self.queue.increment_retry(item["id"], result.get("error", "sync_failed"))
            results.append({"queue_id": item["id"], **result})
        return results


def json_load(value: str) -> dict[str, Any]:
    import json

    return json.loads(value)
