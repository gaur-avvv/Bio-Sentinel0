from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Literal

from pydantic import BaseModel, Field


Severity = Literal["mild", "moderate", "severe"]


class Location(BaseModel):
    state: str
    district: str
    village_or_ward: str | None = None


class SyndromicRecord(BaseModel):
    patient_id: str = Field(min_length=3)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    symptoms: List[str] = Field(default_factory=list)
    syndrome_category: str
    severity: Severity
    onset_days: int = Field(ge=0, le=30)
    age_group: Literal["child", "adult", "older_adult"]
    location: Location
    idsp_flags: List[str] = Field(default_factory=list)
    icd10_codes: List[str] = Field(default_factory=list)
