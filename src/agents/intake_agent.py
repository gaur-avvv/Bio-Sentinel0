from __future__ import annotations

from datetime import datetime, timezone
import re

from src.data.disease_definitions import WHO_IDSP_ALIGNED_SYNDROMES
from src.data.syndromic_schema import Location, SyndromicRecord


class IntakeAgent:
    """Baseline extraction agent with deterministic placeholder logic."""

    SYNDROME_KEYWORDS = {
        "acute_watery_diarrhea": ["diarrhea", "diarrhoea", "dast", "loose motion"],
        "acute_respiratory_infection": [
            "cough",
            "khansi",
            "breath",
            "breathing difficulty",
            "saans",
        ],
        "acute_rash_with_fever": ["rash", "spots", "daaney", "red patches"],
        "acute_neurological_syndrome": ["stiff neck", "confusion", "seizure", "fits"],
        "acute_febrile_illness": ["fever", "bukhar", "jwar", "high temperature"],
    }

    def _infer_onset_days(self, text: str) -> int:
        match = re.search(r"(\d+)\s*(day|days|din)", text)
        if not match:
            return 2
        value = int(match.group(1))
        return max(0, min(30, value))

    def _pick_syndrome(self, text_l: str) -> tuple[str, list[str]]:
        for syndrome, keywords in self.SYNDROME_KEYWORDS.items():
            hit = [kw for kw in keywords if kw in text_l]
            if hit:
                return syndrome, hit[:3]
        return "acute_febrile_illness", ["fever"]

    def extract_from_text(self, text: str, state: str, district: str) -> SyndromicRecord:
        text_l = text.lower()
        syndrome, symptoms = self._pick_syndrome(text_l)
        onset_days = self._infer_onset_days(text_l)

        defs = WHO_IDSP_ALIGNED_SYNDROMES[syndrome]
        return SyndromicRecord(
            patient_id="anon-local",
            timestamp=datetime.now(timezone.utc),
            symptoms=symptoms,
            syndrome_category=syndrome,
            severity="moderate",
            onset_days=onset_days,
            age_group="adult",
            location=Location(state=state, district=district),
            idsp_flags=defs["reportable_flags"],
            icd10_codes=defs["icd10"],
        )
