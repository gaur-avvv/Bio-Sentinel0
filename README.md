# Bio Sentinel

Bio Sentinel is an India-focused, edge-first, agentic disease surveillance platform that converts frontline clinical narratives into structured epidemiological intelligence.

It is designed for low-connectivity environments and supports end-to-end workflows from intake to surveillance analytics, escalation, explainability, and optional sync.

## Vision

Enable faster outbreak signal detection by helping frontline workers and public health teams:

- Capture unstructured encounters in multilingual, code-mixed formats
- Extract structured syndromic signals for reporting and aggregation
- Detect anomalies with transparent scoring logic
- Generate actionable alerts and standards-aligned outputs
- Operate offline-first with queue-based sync behavior

## Production Guide

- Full production blueprint is available in `docs/production_implementation_guide.md`.

## Key Features

### 0. Production Runtime Enhancements

- Pydantic v2 clinical encounter schema for typed validation and derived risk tiering
- Inference backend abstraction with fallback chain (`medgemma_gguf` -> `heuristic`)
- SQLite offline sync queue with retry/backoff metadata
- IDSP sync tool with online sync and offline queue fallback
- Optional trace output for agent-level execution visibility

### 1. India-Adapted Syndromic Intake

- Keyword and phrase-based extraction for English and code-mixed Hindi-style narratives
- Syndrome mapping for key categories such as:
  - acute_watery_diarrhea
  - acute_febrile_illness
  - acute_respiratory_infection
  - acute_rash_with_fever
  - acute_neurological_syndrome
- Onset-day extraction from narrative text
- Structured record output with location, flags, and ICD-style fields

### 2. Surveillance Analytics

- Syndrome-wise aggregation and forecasting baseline
- Poisson and CUSUM-based risk components
- Config-driven thresholds through YAML
- Outbreak risk scoring and anomaly detail output

### 3. Escalation and Interoperability

- Severity-tier alert creation:
  - monitor
  - district_alert
  - state_escalation
- FHIR-like bundle output for interoperability pathways

### 4. ADK-Style Multi-Agent System

Bio Sentinel now includes an advanced internal ADK runtime with specialist agents, tools, and skills.

Agents:

- intake_specialist
- surveillance_analyst
- medical_rag_agent
- multimodal_analyzer
- uncertainty_evaluator
- escalation_coordinator
- api_integration_agent

Tools:

- extract_case
- generate_fhir
- analyze_batch
- create_alert
- retrieve_protocols
- multimodal_fusion
- evaluate_uncertainty
- sync_report

Skills:

- triage_explanation
- risk_explanation
- rag_explanation
- referral_explanation
- workflow_explanation

### 5. Streamlit Full Project Console

The Streamlit workspace provides:

- Single-case pipeline run
- Real-world batch simulation from fixture data
- Multimodal confidence controls (text/audio/image fusion inputs)
- Agent catalog and graph blueprint
- Explainability panels for each stage
- Offline sync queue inspector

### 6. Real-World Test Fixtures and Scenario Testing

- India-focused fixture cases included
- Integration-style tests for cluster behavior and risk movement
- ADK orchestration tests for agent outputs and graph blueprint

### 7. Hosting Ready

- Uvicorn app server entrypoint
- Procfile support
- Render configuration
- Railway configuration
- Dockerfile and dockerignore

### 8. Observability and Monitoring

- Prometheus metrics module at `src/observability/metrics/custom_metrics.py`
- API metrics endpoint: `/metrics`
- Prometheus scrape config: `monitoring/prometheus.yml`
- Grafana provisioning and dashboard JSON under `monitoring/grafana/`
- Docker Compose stack with API, Streamlit, Prometheus, and Grafana

## Project Structure

```text
Bio-Sentinel0/
├── README.md
├── requirements.txt
├── Makefile
├── Procfile
├── Dockerfile
├── .dockerignore
├── railway.json
├── render.yaml
├── streamlit_app.py
├── configs/
│   ├── model_config.yaml
│   └── surveillance_config.yaml
├── docs/
│   ├── technical_overview.md
│   ├── india_adaptation.md
│   └── india_resource_guide.md
├── scripts/
│   ├── generate_training_data.py
│   ├── run_evaluation.py
│   └── run_finetune.py
├── src/
│   ├── api/
│   ├── agents/
│   ├── adk/
│   ├── data/
│   ├── models/
│   ├── sync/
│   └── utils/
└── tests/
    ├── fixtures/
    ├── test_extraction.py
    ├── test_realworld_scenarios.py
    ├── test_adk_orchestration.py
    ├── test_inference_adapter.py
    └── test_offline_sync.py
```

## Core Technology Stack

Backend and API:

- FastAPI
- Uvicorn
- Pydantic

Data and config:

- PyYAML

Testing:

- Pytest
- FastAPI TestClient via httpx

Interactive app:

- Streamlit

Architecture:

- Internal ADK-style runtime for agent, tool, and skill orchestration
- Optional Google ADK bridge detection support
- Clinical state model: `src/adk/state.py`
- Inference adapter layer: `src/models/inference_adapter.py`
- Offline sync engine: `src/sync/offline_queue.py`
- API sync integration tool: `src/agents/api_integration_agent.py`

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the API

```bash
python -m src.api.app
```

Default endpoint checks:

- GET /health
- GET /records
- GET /records/{record_id}
- GET /alerts
- GET /stats/overview
- POST /pipeline/ingest
- POST /pipeline/ingest-batch

## Run Streamlit (Full Workspace)

```bash
streamlit run streamlit_app.py --server.port ${PORT:-8501} --server.address 0.0.0.0
```

## Frontend Integration Section (Web App)

Use this section name in your frontend navigation:

- `Surveillance Integration Hub`

Recommended frontend page blocks:

1. `Case Intake Panel` (single case submit)
2. `Batch Intake Panel` (multiple case submit)
3. `Records Explorer` (filter by state/district/syndrome)
4. `Alerts Feed` (monitor/district/state alerts)
5. `Overview Stats` (counts and top syndromes)

Frontend environment configuration:

- `VITE_API_BASE_URL=https://<your-api-domain>`

Example:

```bash
VITE_API_BASE_URL=https://bio-sentinel-api.up.railway.app
```

Suggested API client (`src/lib/biosentinelApi.ts`):

```ts
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

type IngestRequest = {
  text: string;
  state: string;
  district: string;
};

type BatchIngestRequest = {
  events: IngestRequest[];
};

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    ...init,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody?.error?.message || `API error: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const biosentinelApi = {
  health: () => apiFetch<{ status: string; service: string }>("/health"),

  ingestCase: (payload: IngestRequest) =>
    apiFetch("/pipeline/ingest", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  ingestBatch: (payload: BatchIngestRequest) =>
    apiFetch("/pipeline/ingest-batch", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listRecords: (params?: {
    limit?: number;
    offset?: number;
    state?: string;
    district?: string;
    syndrome?: string;
  }) => {
    const query = new URLSearchParams(
      Object.entries(params || {}).reduce((acc, [k, v]) => {
        if (v !== undefined && v !== null && v !== "") acc[k] = String(v);
        return acc;
      }, {} as Record<string, string>)
    ).toString();
    return apiFetch(`/records${query ? `?${query}` : ""}`);
  },

  getRecord: (recordId: string) => apiFetch(`/records/${recordId}`),

  listAlerts: (params?: { limit?: number; offset?: number; severity?: string }) => {
    const query = new URLSearchParams(
      Object.entries(params || {}).reduce((acc, [k, v]) => {
        if (v !== undefined && v !== null && v !== "") acc[k] = String(v);
        return acc;
      }, {} as Record<string, string>)
    ).toString();
    return apiFetch(`/alerts${query ? `?${query}` : ""}`);
  },

  overviewStats: () => apiFetch("/stats/overview"),
};
```

Frontend route suggestion:

- `/surveillance-integration`

Minimal route component structure:

```tsx
export function SurveillanceIntegrationPage() {
  return (
    <main>
      <h1>Surveillance Integration Hub</h1>
      <section>{/* Case Intake Panel */}</section>
      <section>{/* Batch Intake Panel */}</section>
      <section>{/* Overview Stats */}</section>
      <section>{/* Alerts Feed */}</section>
      <section>{/* Records Explorer */}</section>
    </main>
  );
}
```

Endpoint-to-UI mapping:

- `POST /pipeline/ingest` -> Case Intake Panel
- `POST /pipeline/ingest-batch` -> Batch Intake Panel
- `GET /stats/overview` -> Overview Stats
- `GET /alerts` -> Alerts Feed
- `GET /records` -> Records Explorer
- `GET /records/{record_id}` -> Record details drawer/modal

Integration checklist:

1. Set `VITE_API_BASE_URL` in frontend environment.
2. Add your frontend origin to `CORS_ALLOW_ORIGINS` in API deployment.
3. Build one shared API client module (avoid scattered fetch logic).
4. Surface `X-Request-ID` from API responses in error UI/logging.
5. Add loading, empty, and retry states for each panel.

## Make Commands

```bash
make setup
make run
make run-streamlit
make run-full
make test
make test-realworld
make eval
make data
make lint-check
```

## Testing

Run all tests:

```bash
python -m pytest -q
```

Run specific suites:

```bash
python -m pytest -q tests/test_extraction.py
python -m pytest -q tests/test_realworld_scenarios.py
python -m pytest -q tests/test_adk_orchestration.py
python -m pytest -q tests/test_inference_adapter.py
python -m pytest -q tests/test_offline_sync.py
```

## Configuration

Environment variables:

- `SURVEILLANCE_DB_PATH` (default: `data/surveillance.db`) for persistent encounter/alert storage
- `CORS_ALLOW_ORIGINS` for web client access control

### configs/model_config.yaml

Defines model profiles and inference preferences for local and regional layers.

### configs/surveillance_config.yaml

Defines:

- country and language defaults
- syndrome thresholds
- escalation thresholds
- integration toggles

## ADK Workflow Summary

Single case:

1. intake_specialist extracts structured syndrome record
2. medical_rag_agent retrieves protocol evidence
3. multimodal_analyzer fuses confidence signals
4. uncertainty_evaluator determines referral need
5. surveillance_analyst computes risk summary
6. escalation_coordinator creates alert
7. api_integration_agent syncs or queues payload

Batch case:

1. surveillance_analyst aggregates events
2. medical_rag_agent retrieves dominant syndrome evidence
3. uncertainty_evaluator evaluates referral posture
4. escalation_coordinator emits alert
5. api_integration_agent syncs or queues report

## Explainability Outputs

Bio Sentinel explicitly returns explanation strings for:

- intake triage mapping logic
- risk calculation rationale
- RAG evidence relevance
- referral decision rationale
- workflow stage transitions

## Deployment and Hosting

### Direct Uvicorn

```bash
python -m src.api.app
```

### Procfile Platforms

Procfile start command:

- python -m src.api.app

### Render

Configured via render.yaml with health check path /health.

### Railway

Configured via railway.json with Nixpacks build and /health checks.

### Vercel Web App -> Railway API

If your frontend is hosted on Vercel and API on Railway:

1. Set Railway env variable `CORS_ALLOW_ORIGINS` to include your Vercel URL.
2. Set frontend env variable `VITE_API_BASE_URL` (or equivalent) to Railway API URL.
3. API now returns `X-Request-ID` header and structured error JSON for easier web rendering.

### Docker

```bash
docker build -t bio-sentinel .
docker run -p 8000:8000 bio-sentinel
```

### Local Full Stack (API + Streamlit + Monitoring)

```bash
docker compose up --build
```

Access points:

- API: `http://localhost:8000`
- Streamlit: `http://localhost:8501`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

## Data and Real-World Testing Assets

- Fixture file for India-like multilingual/code-mixed encounters:
  - tests/fixtures/india_realworld_cases.json
- Synthetic training data generator:
  - scripts/generate_training_data.py

## Security and Operational Notes

- Keep secrets in environment variables, never in source files
- Use .env locally and keep it out of version control
- Queue-based sync flow is included for offline-first behavior

## Current Maturity

Implemented and validated baseline includes:

- API and Streamlit workflows
- ADK multi-agent orchestration
- Real-world style fixtures and tests
- Host-ready configuration for common platforms

## Suggested Next Steps

1. Add real authenticated IDSP, IHIP, or ABDM API connectors
2. Replace heuristic extraction with model-backed inference adapter
3. Add role-based access and audit logging
4. Add persistent storage for records and sync queue
5. Add dashboard analytics views (trend charts, district heatmaps)

## Disclaimer

Bio Sentinel is a surveillance support system, not a clinical diagnosis system. Final decisions remain with authorized clinical and public health teams.
