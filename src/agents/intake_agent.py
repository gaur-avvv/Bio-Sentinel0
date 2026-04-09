from __future__ import annotations

from datetime import datetime, timezone
import os
import re
from typing import Any

from src.data.disease_definitions import WHO_IDSP_ALIGNED_SYNDROMES
from src.data.syndromic_schema import Location, SyndromicRecord
from src.models.inference_adapter import InferenceBackend, get_inference_backend


class IntakeAgent:
    """Baseline extraction agent with deterministic placeholder logic."""

    VALID_SEVERITIES = {"mild", "moderate", "severe"}

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

    def __init__(self, use_model: bool | None = None, preferred_backend: str | None = None) -> None:
        env_use_model = os.getenv("INTAKE_USE_MODEL", "false").lower() in {"1", "true", "yes"}
        self.use_model = env_use_model if use_model is None else use_model
        self.preferred_backend = preferred_backend or os.getenv("INTAKE_INFERENCE_BACKEND", "medgemma_gguf")
        self.backend: InferenceBackend | None = None
        if self.use_model:
            self.backend = get_inference_backend(preferred=self.preferred_backend)

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

    def predict_case(self, text: str, state: str, district: str, language: str = "eng") -> dict[str, Any]:
        """Return a prediction payload combining model extraction and deterministic hints."""
        text_l = text.lower()
        keyword_syndrome, keyword_symptoms = self._pick_syndrome(text_l)
        keyword_onset = self._infer_onset_days(text_l)
        keyword_confidence = 0.62

        model_result: dict[str, Any] = {}
        model_name = "heuristic"
        if self.backend is not None:
            model_result = self.backend.extract(
                text=text,
                language=language,
                context={"state": state, "district": district},
            )
            model_name = self.backend.get_capabilities().get("backend", model_name)

        model_syndrome = model_result.get("syndrome")
        model_conf = float(model_result.get("confidence", 0.0) or 0.0)
        syndrome = keyword_syndrome
        source = "keyword"
        confidence = keyword_confidence
        symptoms = keyword_symptoms

        if isinstance(model_syndrome, str) and model_syndrome in WHO_IDSP_ALIGNED_SYNDROMES:
            # Pick model output only when confidence is at least comparable to deterministic hints.
            if model_conf >= (keyword_confidence - 0.05):
                syndrome = model_syndrome
                source = "model"
                confidence = max(model_conf, keyword_confidence)
                model_symptoms = model_result.get("symptoms")
                if isinstance(model_symptoms, list) and model_symptoms:
                    symptoms = [str(s) for s in model_symptoms][:5]

        onset = keyword_onset
        raw_onset = model_result.get("onset_days_ago")
        if isinstance(raw_onset, int):
            onset = max(0, min(30, raw_onset))

        severity = str(model_result.get("severity", "moderate"))
        if severity not in self.VALID_SEVERITIES:
            severity = "moderate"

        return {
            "syndrome": syndrome,
            "severity": severity,
            "symptoms": symptoms,
            "onset_days": onset,
            "confidence": round(confidence, 3),
            "source": source,
            "model_backend": model_name,
            "model_raw": model_result,
        }

    def extract_from_text(self, text: str, state: str, district: str) -> SyndromicRecord:
        text_l = text.lower()
        syndrome, symptoms = self._pick_syndrome(text_l)
        onset_days = self._infer_onset_days(text_l)
        severity = "moderate"

        if self.use_model:
            prediction = self.predict_case(text=text, state=state, district=district)
            syndrome = str(prediction.get("syndrome", syndrome))
            symptoms = prediction.get("symptoms", symptoms)
            onset_days = int(prediction.get("onset_days", onset_days))
            severity = str(prediction.get("severity", severity))

        defs = WHO_IDSP_ALIGNED_SYNDROMES[syndrome]
        return SyndromicRecord(
            patient_id="anon-local",
            timestamp=datetime.now(timezone.utc),
            symptoms=symptoms,
            syndrome_category=syndrome,
            severity=severity,
            onset_days=onset_days,
            age_group="adult",
            location=Location(state=state, district=district),
            idsp_flags=defs["reportable_flags"],
            icd10_codes=defs["icd10"],
        )
