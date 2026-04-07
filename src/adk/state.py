from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
import uuid

from pydantic import BaseModel, Field, computed_field


class ClinicalEncounter(BaseModel):
    """Structured clinical record from frontline intake."""

    id: str = Field(default_factory=lambda: f"enc_{uuid.uuid4().hex[:8]}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    abha_number: str | None = Field(None, pattern=r"^[0-9]{4}-[0-9]{4}-[0-9]{4}$")
    age_years: int | None = Field(None, ge=0, le=120)
    sex: Literal["M", "F", "Other"] | None = None

    state_code: str = "IN"
    district: str
    village: str | None = None
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)

    narrative_text: str
    narrative_language: str = "hin"
    code_mixed: bool = False

    syndrome: str | None = None
    severity: Literal["mild", "moderate", "severe", "critical"] | None = None
    icd10_codes: list[str] = Field(default_factory=list)
    symptoms: list[str] = Field(default_factory=list)
    onset_days_ago: int | None = Field(None, ge=0, le=90)

    audio_uri: str | None = None
    image_uris: list[str] = Field(default_factory=list)

    confidence_score: float = Field(ge=0.0, le=1.0, default=0.5)
    needs_referral: bool = False
    referral_reason: str | None = None

    idsp_report_id: str | None = None
    ihip_thread_id: str | None = None
    sync_status: Literal["pending", "synced", "failed", "offline_queued"] = "pending"

    @computed_field
    @property
    def risk_tier(self) -> Literal["green", "yellow", "orange", "red"]:
        high_priority = {
            "acute_hemorrhagic_fever",
            "acute_flaccid_paralysis",
            "neonatal_tetanus",
        }
        if self.syndrome in high_priority and self.confidence_score > 0.7:
            return "red"
        if self.severity in {"severe", "critical"}:
            return "orange" if self.confidence_score > 0.6 else "yellow"
        return "green"
