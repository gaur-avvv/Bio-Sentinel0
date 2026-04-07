from __future__ import annotations

import json
from pathlib import Path

from src.agents.intake_agent import IntakeAgent
from src.agents.surveillance_agent import SurveillanceAgent


def _load_cases() -> list[dict[str, str]]:
    fixture = Path("tests/fixtures/india_realworld_cases.json")
    return json.loads(fixture.read_text(encoding="utf-8"))


def test_realworld_case_extraction_matches_expected_syndromes() -> None:
    agent = IntakeAgent()
    cases = _load_cases()

    for case in cases:
        record = agent.extract_from_text(
            text=case["text"],
            state=case["state"],
            district=case["district"],
        )
        assert record.syndrome_category == case["expected_syndrome"]


def test_realworld_cluster_produces_higher_risk_than_single_case() -> None:
    intake = IntakeAgent()
    analytics = SurveillanceAgent()
    cases = _load_cases()

    single = intake.extract_from_text(
        text=cases[0]["text"],
        state=cases[0]["state"],
        district=cases[0]["district"],
    )
    baseline_summary = analytics.summarize([single])

    # Simulate a district-time window where respiratory-like complaints surge.
    cluster_texts = [
        "Fever with cough and breathing difficulty for 2 days",
        "Patient ko khansi aur saans ki takleef 3 din se",
        "Cough, breathlessness and fever since 1 day",
        "Khansi with breath issue for 2 din",
        "Severe cough and breathing difficulty 4 days",
    ]

    clustered_records = [
        intake.extract_from_text(text=t, state="Uttar Pradesh", district="Lucknow")
        for t in cluster_texts
    ]
    cluster_summary = analytics.summarize(clustered_records)

    assert cluster_summary["total_records"] == len(cluster_texts)
    assert cluster_summary["outbreak_risk_score"] >= baseline_summary["outbreak_risk_score"]
    assert "acute_respiratory_infection" in cluster_summary["syndrome_counts"]
