from __future__ import annotations

from src.data.syndromic_schema import SyndromicRecord


def to_fhir_like_bundle(record: SyndromicRecord) -> dict:
    """Generate a compact FHIR-like surveillance payload."""
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "status": "final",
                    "code": {"text": record.syndrome_category},
                    "subject": {"reference": f"Patient/{record.patient_id}"},
                    "valueString": ", ".join(record.symptoms),
                    "effectiveDateTime": record.timestamp.isoformat(),
                }
            }
        ],
    }
