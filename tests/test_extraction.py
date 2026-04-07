from src.agents.intake_agent import IntakeAgent
from fastapi.testclient import TestClient

from src.api.app import app


client = TestClient(app)


def test_extract_respiratory_syndrome() -> None:
    agent = IntakeAgent()
    record = agent.extract_from_text(
        "Fever with cough and breathing difficulty",
        state="Maharashtra",
        district="Pune",
    )
    assert record.syndrome_category == "acute_respiratory_infection"
    assert "ari_cluster_watch" in record.idsp_flags


def test_extract_diarrhea_syndrome() -> None:
    agent = IntakeAgent()
    record = agent.extract_from_text(
        "Watery diarrhea for two days",
        state="Bihar",
        district="Patna",
    )
    assert record.syndrome_category == "acute_watery_diarrhea"
    assert record.onset_days >= 0


def test_extract_code_mixed_keywords_and_onset_days() -> None:
    agent = IntakeAgent()
    record = agent.extract_from_text(
        "Patient ko bukhar aur khansi hai 3 din se",
        state="Uttar Pradesh",
        district="Lucknow",
    )
    assert record.syndrome_category in {
        "acute_respiratory_infection",
        "acute_febrile_illness",
    }
    assert record.onset_days == 3


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"


def test_root_endpoint() -> None:
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "/pipeline/ingest" in payload["endpoints"]


def test_metrics_endpoint() -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "biosentinel_http_requests_total" in body


def test_cors_preflight_for_web_app() -> None:
    response = client.options(
        "/pipeline/ingest",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code in {200, 204}
    assert "access-control-allow-origin" in {k.lower() for k in response.headers.keys()}


def test_batch_ingest_endpoint() -> None:
    response = client.post(
        "/pipeline/ingest-batch",
        json={
            "events": [
                {
                    "text": "Watery diarrhea for two days",
                    "state": "Bihar",
                    "district": "Patna",
                },
                {
                    "text": "Fever with cough and breathing difficulty for 2 days",
                    "state": "Maharashtra",
                    "district": "Pune",
                },
            ]
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_records"] == 2
    assert isinstance(payload["summary"]["anomaly_details"], dict)
