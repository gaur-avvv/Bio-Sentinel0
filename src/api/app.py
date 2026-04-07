from __future__ import annotations

import os
import time
import uuid

from fastapi import FastAPI
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


class IngestRequest(BaseModel):
    text: str
    state: str
    district: str


class BatchIngestRequest(BaseModel):
    events: list[IngestRequest]


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
        "endpoints": ["/health", "/pipeline/ingest", "/pipeline/ingest-batch", "/metrics"],
    }


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


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
    ALERTS_GENERATED.labels(
        alert_type="single_ingest",
        severity=alert.get("severity", "monitor"),
        escalation_level=alert.get("severity", "monitor"),
    ).inc()
    return {
        "record": record.model_dump(mode="json"),
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
        "records": [record.model_dump(mode="json") for record in records],
        "summary": summary,
        "alert": alert,
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.api.app:app", host="0.0.0.0", port=port, reload=False)
