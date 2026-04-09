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


def test_predict_endpoint_returns_prediction_payload() -> None:
    response = client.post(
        "/pipeline/predict",
        json={
            "text": "Patient has fever and cough for 2 days",
            "state": "Maharashtra",
            "district": "Pune",
            "language": "eng",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "prediction" in payload
    assert payload["prediction"]["syndrome"] in {
        "acute_febrile_illness",
        "acute_respiratory_infection",
        "acute_watery_diarrhea",
        "acute_rash_with_fever",
        "acute_neurological_syndrome",
    }
    assert "model_backend" in payload["prediction"]


def test_manual_record_create_endpoint() -> None:
    response = client.post(
        "/records/manual",
        json={
            "record": {
                "patient_id": "anon-manual",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "symptoms": ["fever"],
                "syndrome_category": "acute_febrile_illness",
                "severity": "moderate",
                "onset_days": 2,
                "age_group": "adult",
                "location": {"state": "Delhi", "district": "New Delhi"},
                "idsp_flags": ["fever_cluster_watch"],
                "icd10_codes": ["R50"],
            }
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["record_id"].startswith("rec_")
    assert payload["record"]["location"]["state"] == "Delhi"


def test_records_alerts_and_stats_endpoints() -> None:
    ingest_response = client.post(
        "/pipeline/ingest",
        json={
            "text": "Fever with cough and breathing difficulty for 2 days",
            "state": "Maharashtra",
            "district": "Pune",
        },
    )
    assert ingest_response.status_code == 200
    ingest_payload = ingest_response.json()
    record_id = ingest_payload["record"]["record_id"]
    alert_id = ingest_payload["alert"]["alert_id"]

    records_response = client.get("/records", params={"state": "Maharashtra", "limit": 20})
    assert records_response.status_code == 200
    records_payload = records_response.json()
    assert records_payload["count"] >= 1
    assert any(record.get("record_id") == record_id for record in records_payload["records"])

    record_response = client.get(f"/records/{record_id}")
    assert record_response.status_code == 200
    assert record_response.json()["record_id"] == record_id

    alerts_response = client.get("/alerts", params={"limit": 20})
    assert alerts_response.status_code == 200
    alerts_payload = alerts_response.json()
    assert alerts_payload["count"] >= 1
    assert any(alert.get("alert_id") == alert_id for alert in alerts_payload["alerts"])

    stats_response = client.get("/stats/overview")
    assert stats_response.status_code == 200
    stats_payload = stats_response.json()
    assert "total_records" in stats_payload
    assert "total_alerts" in stats_payload


def test_get_record_not_found() -> None:
    response = client.get("/records/rec_non_existent")
    assert response.status_code == 404


def test_supabase_health_without_configuration() -> None:
    response = client.get("/supabase/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["ok"] is False


def test_supabase_records_returns_error_without_configuration() -> None:
    response = client.get("/supabase/records")
    assert response.status_code == 503


def test_railway_health_without_configuration() -> None:
    response = client.get("/railway/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["ok"] is False


def test_railway_records_returns_error_without_configuration() -> None:
    response = client.get("/railway/records")
    assert response.status_code == 503
