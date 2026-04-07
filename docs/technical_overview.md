# Bio Sentinel Technical Overview

## System Objective

Bio Sentinel converts unstructured frontline health encounter signals into structured surveillance intelligence with low-latency local operation and optional upstream synchronization.

## Design Principles

- Edge-first intake and preprocessing
- Structured extraction for machine-actionable epidemiology
- Config-driven anomaly thresholds by syndrome and region
- Explainable alert outputs with evidence traces

## Agentic Components

1. Intake Agent
- Ingests transcript text and optional image cues
- Extracts symptom entities, severity, onset, demographics, and location metadata
- Produces validated `SyndromicRecord` objects

2. Surveillance Agent
- Aggregates records by syndrome and geography over sliding windows
- Applies Poisson and CUSUM rules for aberration detection
- Produces anomaly summaries and risk score estimates

3. Alert Agent
- Formats district/state alerts with confidence and evidence
- Emits FHIR-style bundles for interoperable exchange
- Generates public-facing advisory drafts with evidence-linked risk rationale

## India Alignment

- Mapping to IDSP-like syndrome categories
- IHIP-oriented data export and synchronization hooks
- Multilingual and code-mixed text normalization path
- State-level override support through YAML configuration

## Deployment Modes

1. Edge-only mode
- Intake and anomaly checks run entirely local
- Local cache used for deferred sync

2. Hybrid mode
- Edge nodes perform extraction
- Regional server performs heavier analytics and coordinated alerts

## Security and Privacy Baseline

- De-identification before sync
- Minimal data retention defaults
- Audit events for extract, score, and alert actions

## Current Baseline Scope

- API scaffold with health and pipeline endpoints
- Batch ingest API for multi-event signal aggregation
- Config-driven thresholding by syndrome from YAML
- Multilingual and code-mixed keyword extraction baseline
- Statistical utility baseline for Poisson/CUSUM with anomaly details
- Contract and API tests for extraction and pipeline behavior
