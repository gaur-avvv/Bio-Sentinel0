from __future__ import annotations

from src.data.syndromic_schema import SyndromicRecord
from src.utils.fhir_generator import to_fhir_like_bundle


class AlertAgent:
    def build_alert(self, summary: dict) -> dict:
        score = float(summary.get("outbreak_risk_score", 0.0))
        severity = "monitor"
        if score >= 0.8:
            severity = "state_escalation"
        elif score >= 0.65:
            severity = "district_alert"

        return {
            "severity": severity,
            "score": score,
            "message": "Syndromic anomaly detected" if score >= 0.65 else "No major anomaly",
            "evidence": summary,
        }

    def to_fhir(self, record: SyndromicRecord) -> dict:
        return to_fhir_like_bundle(record)
