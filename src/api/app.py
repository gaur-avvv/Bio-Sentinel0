from __future__ import annotations

import os
import time
import uuid

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from src.agents.alert_agent import AlertAgent
from src.agents.intake_agent import IntakeAgent
from src.agents.surveillance_agent import SurveillanceAgent
from src.data.railway_store import RailwayStoreError, RailwaySurveillanceStore
from src.data.surveillance_store import SurveillanceStore
from src.data.supabase_store import SupabaseStoreError, SupabaseSurveillanceStore
from src.data.syndromic_schema import SyndromicRecord
from src.observability.metrics.custom_metrics import (
    ALERTS_GENERATED,
    ENCOUNTERS_BY_SYNDROME,
    record_http_request,
)

app = FastAPI(title="Bio Sentinel API", version="0.1.0")

_allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:3000,http://localhost:5173,https://*.vercel.app",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

intake_agent = IntakeAgent()
surveillance_agent = SurveillanceAgent()
alert_agent = AlertAgent()
surveillance_store = SurveillanceStore(db_path=os.getenv("SURVEILLANCE_DB_PATH", "data/surveillance.db"))
supabase_store = SupabaseSurveillanceStore(
    url=os.getenv("SUPABASE_URL"),
    service_key=os.getenv("SUPABASE_KEY"),
    records_table=os.getenv("SUPABASE_RECORDS_TABLE", "encounters"),
    alerts_table=os.getenv("SUPABASE_ALERTS_TABLE", "alerts"),
)
railway_store = RailwaySurveillanceStore(
    database_url=os.getenv("RAILWAY_DATABASE_URL") or os.getenv("DATABASE_URL"),
    records_table=os.getenv("RAILWAY_RECORDS_TABLE", "encounters"),
    alerts_table=os.getenv("RAILWAY_ALERTS_TABLE", "alerts"),
)
SUPABASE_WRITE_THROUGH = os.getenv("SUPABASE_WRITE_THROUGH", "false").lower() in {"1", "true", "yes"}
RAILWAY_WRITE_THROUGH = os.getenv("RAILWAY_WRITE_THROUGH", "false").lower() in {"1", "true", "yes"}


class IngestRequest(BaseModel):
    text: str
    state: str
    district: str


class BatchIngestRequest(BaseModel):
    events: list[IngestRequest]


class PredictRequest(BaseModel):
    text: str
    state: str
    district: str
    language: str = "eng"


class RecordCreateRequest(BaseModel):
    record: SyndromicRecord


def _write_through_supabase_record(record_payload: dict) -> None:
    if not (SUPABASE_WRITE_THROUGH and supabase_store.enabled):
        return
    try:
        supabase_store.save_record_payload(record_payload)
    except SupabaseStoreError:
        # Keep local ingest resilient if cloud write-through is unavailable.
        return


def _write_through_supabase_alert(alert_payload: dict, source: str, linked_record_id: str | None = None) -> None:
    if not (SUPABASE_WRITE_THROUGH and supabase_store.enabled):
        return
    try:
        supabase_store.save_alert(alert_payload, source=source, linked_record_id=linked_record_id)
    except SupabaseStoreError:
        return


def _write_through_railway_record(record_payload: dict) -> None:
    if not (RAILWAY_WRITE_THROUGH and railway_store.enabled):
        return
    try:
        railway_store.save_record_payload(record_payload)
    except RailwayStoreError:
        return


def _write_through_railway_alert(alert_payload: dict, source: str, linked_record_id: str | None = None) -> None:
    if not (RAILWAY_WRITE_THROUGH and railway_store.enabled):
        return
    try:
        railway_store.save_alert(alert_payload, source=source, linked_record_id=linked_record_id)
    except RailwayStoreError:
        return


@app.middleware("http")
async def metrics_middleware(request, call_next):
    started = time.perf_counter()
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id

    response = await call_next(request)
    duration = time.perf_counter() - started
    record_http_request(
        method=request.method,
        endpoint=request.url.path,
        status=str(response.status_code),
        duration_seconds=duration,
        agent="api",
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "type": "validation_error",
                "message": "Request validation failed",
                "details": exc.errors(),
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "type": "internal_error",
                "message": "Unexpected server error",
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "bio-sentinel"}


@app.get("/")
def root() -> dict:
    return {
        "name": "bio-sentinel-api",
        "status": "ok",
        "endpoints": [
            "/health",
            "/metrics",
            "/pipeline/predict",
            "/pipeline/ingest",
            "/pipeline/ingest-batch",
            "/records/manual",
            "/records",
            "/records/{record_id}",
            "/alerts",
            "/stats/overview",
            "/supabase/health",
            "/supabase/records",
            "/supabase/records/{record_id}",
            "/supabase/alerts",
            "/supabase/sync/records",
            "/supabase/sync/alerts",
            "/railway/health",
            "/railway/records",
            "/railway/records/{record_id}",
            "/railway/alerts",
            "/railway/sync/records",
            "/railway/sync/alerts",
        ],
    }


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/pipeline/predict")
def predict(payload: PredictRequest) -> dict:
    prediction = intake_agent.predict_case(
        text=payload.text,
        state=payload.state,
        district=payload.district,
        language=payload.language,
    )
    return {
        "prediction": prediction,
        "inference_enabled": intake_agent.use_model,
    }


@app.post("/pipeline/ingest")
def ingest(payload: IngestRequest) -> dict:
    record = intake_agent.extract_from_text(
        text=payload.text,
        state=payload.state,
        district=payload.district,
    )
    ENCOUNTERS_BY_SYNDROME.labels(
        syndrome=record.syndrome_category,
        state=record.location.state,
        district=record.location.district,
        risk_tier="green",
    ).inc()
    summary = surveillance_agent.summarize([record])
    alert = alert_agent.build_alert(summary)
    record_id = surveillance_store.save_record(record)
    alert_id = surveillance_store.save_alert(alert, source="single_ingest", linked_record_id=record_id)
    _write_through_supabase_record({**record.model_dump(mode="json"), "record_id": record_id})
    _write_through_supabase_alert(alert, source="single_ingest", linked_record_id=record_id)
    _write_through_railway_record({**record.model_dump(mode="json"), "record_id": record_id})
    _write_through_railway_alert(alert, source="single_ingest", linked_record_id=record_id)
    alert["alert_id"] = alert_id
    ALERTS_GENERATED.labels(
        alert_type="single_ingest",
        severity=alert.get("severity", "monitor"),
        escalation_level=alert.get("severity", "monitor"),
    ).inc()
    return {
        "record": {**record.model_dump(mode="json"), "record_id": record_id},
        "summary": summary,
        "alert": alert,
        "fhir": alert_agent.to_fhir(record),
    }


@app.post("/pipeline/ingest-batch")
def ingest_batch(payload: BatchIngestRequest) -> dict:
    records = [
        intake_agent.extract_from_text(
            text=event.text,
            state=event.state,
            district=event.district,
        )
        for event in payload.events
    ]
    summary = surveillance_agent.summarize(records)
    alert = alert_agent.build_alert(summary)
    record_ids: list[str] = []
    for record in records:
        record_ids.append(surveillance_store.save_record(record))
    alert_id = surveillance_store.save_alert(alert, source="batch_ingest")
    alert["alert_id"] = alert_id
    if SUPABASE_WRITE_THROUGH and supabase_store.enabled:
        for idx, record in enumerate(records):
            _write_through_supabase_record({**record.model_dump(mode="json"), "record_id": record_ids[idx]})
        _write_through_supabase_alert(alert, source="batch_ingest")
    if RAILWAY_WRITE_THROUGH and railway_store.enabled:
        for idx, record in enumerate(records):
            _write_through_railway_record({**record.model_dump(mode="json"), "record_id": record_ids[idx]})
        _write_through_railway_alert(alert, source="batch_ingest")
    for record in records:
        ENCOUNTERS_BY_SYNDROME.labels(
            syndrome=record.syndrome_category,
            state=record.location.state,
            district=record.location.district,
            risk_tier="green",
        ).inc()
    ALERTS_GENERATED.labels(
        alert_type="batch_ingest",
        severity=alert.get("severity", "monitor"),
        escalation_level=alert.get("severity", "monitor"),
    ).inc()
    return {
        "records": [
            {**record.model_dump(mode="json"), "record_id": record_ids[idx]}
            for idx, record in enumerate(records)
        ],
        "summary": summary,
        "alert": alert,
    }


@app.post("/records/manual")
def create_manual_record(payload: RecordCreateRequest) -> dict:
    record_id = surveillance_store.save_record(payload.record)
    record_json = {**payload.record.model_dump(mode="json"), "record_id": record_id}
    _write_through_supabase_record(record_json)
    _write_through_railway_record(record_json)
    return {"record_id": record_id, "record": record_json}


@app.get("/records")
def list_records(
    limit: int = 50,
    offset: int = 0,
    state: str | None = None,
    district: str | None = None,
    syndrome: str | None = None,
) -> dict:
    records = surveillance_store.list_records(
        limit=limit,
        offset=offset,
        state=state,
        district=district,
        syndrome=syndrome,
    )
    return {
        "count": len(records),
        "limit": limit,
        "offset": offset,
        "filters": {
            "state": state,
            "district": district,
            "syndrome": syndrome,
        },
        "records": records,
    }


@app.get("/records/{record_id}")
def get_record(record_id: str) -> dict:
    record = surveillance_store.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail={"message": "Record not found", "record_id": record_id})
    return record


@app.get("/alerts")
def list_alerts(limit: int = 50, offset: int = 0, severity: str | None = None) -> dict:
    alerts = surveillance_store.list_alerts(limit=limit, offset=offset, severity=severity)
    return {
        "count": len(alerts),
        "limit": limit,
        "offset": offset,
        "severity": severity,
        "alerts": alerts,
    }


@app.get("/stats/overview")
def overview_stats() -> dict:
    return surveillance_store.get_overview_stats()


@app.get("/supabase/health")
def supabase_health() -> dict:
    return supabase_store.health()


@app.get("/supabase/records")
def list_supabase_records(
    limit: int = 50,
    offset: int = 0,
    state: str | None = None,
    district: str | None = None,
    syndrome: str | None = None,
) -> dict:
    try:
        records = supabase_store.list_records(
            limit=limit,
            offset=offset,
            state=state,
            district=district,
            syndrome=syndrome,
        )
    except SupabaseStoreError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc

    return {
        "count": len(records),
        "limit": limit,
        "offset": offset,
        "filters": {
            "state": state,
            "district": district,
            "syndrome": syndrome,
        },
        "records": records,
    }


@app.get("/supabase/records/{record_id}")
def get_supabase_record(record_id: str) -> dict:
    try:
        record = supabase_store.get_record(record_id)
    except SupabaseStoreError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc
    if not record:
        raise HTTPException(status_code=404, detail={"message": "Record not found", "record_id": record_id})
    return record


@app.get("/supabase/alerts")
def list_supabase_alerts(limit: int = 50, offset: int = 0, severity: str | None = None) -> dict:
    try:
        alerts = supabase_store.list_alerts(limit=limit, offset=offset, severity=severity)
    except SupabaseStoreError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc
    return {
        "count": len(alerts),
        "limit": limit,
        "offset": offset,
        "severity": severity,
        "alerts": alerts,
    }


@app.post("/supabase/sync/records")
def sync_records_to_supabase(limit: int = Query(200, ge=1, le=2000), offset: int = Query(0, ge=0)) -> dict:
    if not supabase_store.enabled:
        raise HTTPException(status_code=400, detail={"message": "Supabase is not configured"})

    local_records = surveillance_store.list_records(limit=limit, offset=offset)
    synced = 0
    failed = 0
    for record in local_records:
        try:
            supabase_store.save_record_payload(record)
            synced += 1
        except SupabaseStoreError:
            failed += 1
    return {
        "synced": synced,
        "failed": failed,
        "attempted": len(local_records),
    }


@app.post("/supabase/sync/alerts")
def sync_alerts_to_supabase(limit: int = Query(200, ge=1, le=2000), offset: int = Query(0, ge=0)) -> dict:
    if not supabase_store.enabled:
        raise HTTPException(status_code=400, detail={"message": "Supabase is not configured"})

    local_alerts = surveillance_store.list_alerts(limit=limit, offset=offset)
    synced = 0
    failed = 0
    for alert in local_alerts:
        try:
            supabase_store.save_alert(
                alert,
                source=str(alert.get("source", "sqlite_sync")),
                linked_record_id=alert.get("linked_record_id"),
            )
            synced += 1
        except SupabaseStoreError:
            failed += 1
    return {
        "synced": synced,
        "failed": failed,
        "attempted": len(local_alerts),
    }


@app.get("/railway/health")
def railway_health() -> dict:
    return railway_store.health()


@app.get("/railway/records")
def list_railway_records(
    limit: int = 50,
    offset: int = 0,
    state: str | None = None,
    district: str | None = None,
    syndrome: str | None = None,
) -> dict:
    try:
        records = railway_store.list_records(
            limit=limit,
            offset=offset,
            state=state,
            district=district,
            syndrome=syndrome,
        )
    except RailwayStoreError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc

    return {
        "count": len(records),
        "limit": limit,
        "offset": offset,
        "filters": {
            "state": state,
            "district": district,
            "syndrome": syndrome,
        },
        "records": records,
    }


@app.get("/railway/records/{record_id}")
def get_railway_record(record_id: str) -> dict:
    try:
        record = railway_store.get_record(record_id)
    except RailwayStoreError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc
    if not record:
        raise HTTPException(status_code=404, detail={"message": "Record not found", "record_id": record_id})
    return record


@app.get("/railway/alerts")
def list_railway_alerts(limit: int = 50, offset: int = 0, severity: str | None = None) -> dict:
    try:
        alerts = railway_store.list_alerts(limit=limit, offset=offset, severity=severity)
    except RailwayStoreError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc
    return {
        "count": len(alerts),
        "limit": limit,
        "offset": offset,
        "severity": severity,
        "alerts": alerts,
    }


@app.post("/railway/sync/records")
def sync_records_to_railway(limit: int = Query(200, ge=1, le=2000), offset: int = Query(0, ge=0)) -> dict:
    if not railway_store.enabled:
        raise HTTPException(status_code=400, detail={"message": "Railway storage is not configured"})

    local_records = surveillance_store.list_records(limit=limit, offset=offset)
    synced = 0
    failed = 0
    for record in local_records:
        try:
            railway_store.save_record_payload(record)
            synced += 1
        except RailwayStoreError:
            failed += 1
    return {
        "synced": synced,
        "failed": failed,
        "attempted": len(local_records),
    }


@app.post("/railway/sync/alerts")
def sync_alerts_to_railway(limit: int = Query(200, ge=1, le=2000), offset: int = Query(0, ge=0)) -> dict:
    if not railway_store.enabled:
        raise HTTPException(status_code=400, detail={"message": "Railway storage is not configured"})

    local_alerts = surveillance_store.list_alerts(limit=limit, offset=offset)
    synced = 0
    failed = 0
    for alert in local_alerts:
        try:
            railway_store.save_alert(
                alert,
                source=str(alert.get("source", "sqlite_sync")),
                linked_record_id=alert.get("linked_record_id"),
            )
            synced += 1
        except RailwayStoreError:
            failed += 1
    return {
        "synced": synced,
        "failed": failed,
        "attempted": len(local_alerts),
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.api.app:app", host="0.0.0.0", port=port, reload=False)
