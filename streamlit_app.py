from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from src.adk import BioSentinelADK, GoogleADKBridge


st.set_page_config(page_title="Bio Sentinel Live Console", layout="wide")

adk = BioSentinelADK()
google_adk = GoogleADKBridge()


def run_single_case(
    text: str,
    state: str,
    district: str,
    audio_conf: float,
    image_conf: float,
    online_sync: bool,
) -> dict:
    return adk.run_single_pipeline(
        text=text,
        state=state,
        district=district,
        audio_conf=audio_conf,
        image_conf=image_conf,
        online_sync=online_sync,
        collect_trace=True,
    )


def run_batch_cases(events: list[dict[str, str]], online_sync: bool) -> dict:
    return adk.run_batch_pipeline(events, online_sync=online_sync)


def load_fixture_cases() -> list[dict[str, str]]:
    fixture = Path("tests/fixtures/india_realworld_cases.json")
    if not fixture.exists():
        return []
    return json.loads(fixture.read_text(encoding="utf-8"))


st.title("Bio Sentinel: Real-Time Surveillance Console")
st.caption("ADK-enabled multi-agent workspace for India-focused syndromic surveillance.")

with st.expander("Runtime Status", expanded=False):
    st.json(
        {
            "google_adk": google_adk.status(),
            "internal_adk": "active",
            "queue_length": len(adk.sync_queue),
        }
    )

tab_single, tab_batch, tab_adk, tab_queue = st.tabs(
    ["Single Case", "Real-World Batch", "ADK Agents & Skills", "Sync Queue"]
)

with tab_single:
    st.subheader("Single Encounter Intake")
    default_text = "Patient ko bukhar aur khansi hai 3 din se"
    text = st.text_area("Clinical Narrative", value=default_text, height=120)
    col1, col2 = st.columns(2)
    with col1:
        state = st.text_input("State", value="Uttar Pradesh")
    with col2:
        district = st.text_input("District", value="Lucknow")
    col3, col4, col5 = st.columns(3)
    with col3:
        audio_conf = st.slider("Audio Confidence", 0.0, 1.0, 0.2, 0.05)
    with col4:
        image_conf = st.slider("Image Confidence", 0.0, 1.0, 0.1, 0.05)
    with col5:
        online_sync = st.checkbox("Online Sync", value=False)

    if st.button("Run Single Pipeline", type="primary"):
        result = run_single_case(
            text=text,
            state=state,
            district=district,
            audio_conf=audio_conf,
            image_conf=image_conf,
            online_sync=online_sync,
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Records", result["summary"]["total_records"])
        c2.metric("Risk Score", result["summary"]["outbreak_risk_score"])
        c3.metric("Alert Severity", result["alert"]["severity"])
        st.write("Syndrome Counts")
        st.json(result["summary"].get("syndrome_counts", {}))
        st.write("Anomaly Details")
        st.json(result["summary"].get("anomaly_details", {}))
        st.write("FHIR Output")
        st.json(result["fhir"])
        st.write("Protocol Evidence")
        st.json(result["protocols"])
        st.write("Multimodal Fusion")
        st.json(result["fusion"])
        st.write("Uncertainty Evaluation")
        st.json(result["uncertainty"])
        st.write("API Sync Result")
        st.json(result["sync"])
        st.write("ADK Explanations")
        st.info(result["explanations"]["triage"])
        st.info(result["explanations"]["risk"])
        st.info(result["explanations"]["rag"])
        st.info(result["explanations"]["referral"])
        st.info(result["explanations"]["workflow"])
        st.write("Agent Trace")
        st.json(result.get("trace", []))

with tab_batch:
    st.subheader("Batch Simulation from Real-World Fixture")
    cases = load_fixture_cases()
    st.write(f"Loaded {len(cases)} fixture events")
    batch_online_sync = st.checkbox("Online Sync (Batch)", value=False)
    if cases:
        st.dataframe(cases, use_container_width=True)

    if st.button("Run Batch Pipeline", type="primary"):
        if not cases:
            st.warning("No fixture cases found in tests/fixtures/india_realworld_cases.json")
        else:
            result = run_batch_cases(cases, online_sync=batch_online_sync)
            c1, c2, c3 = st.columns(3)
            c1.metric("Batch Records", result["summary"]["total_records"])
            c2.metric("Risk Score", result["summary"]["outbreak_risk_score"])
            c3.metric("Alert Severity", result["alert"]["severity"])
            st.write("Syndrome Counts")
            st.json(result["summary"].get("syndrome_counts", {}))
            st.write("Anomaly Details")
            st.json(result["summary"].get("anomaly_details", {}))
            st.write("Protocol Evidence")
            st.json(result["protocols"])
            st.write("Uncertainty Evaluation")
            st.json(result["uncertainty"])
            st.write("API Sync Result")
            st.json(result["sync"])
            st.write("ADK Explanations")
            st.info(result["explanations"]["risk"])
            st.info(result["explanations"]["rag"])
            st.info(result["explanations"]["referral"])
            st.info(result["explanations"]["workflow"])

with tab_adk:
    st.subheader("Agent Catalog and Runtime Skills")
    catalog = adk.list_agent_catalog()
    st.dataframe(catalog, use_container_width=True)

    st.markdown("### Agent Workflow")
    st.json(adk.export_graph_blueprint())

    st.markdown("### Skill Intents")
    st.markdown(
        "- **triage_explanation**: why a syndrome was chosen for a case.\n"
        "- **risk_explanation**: how anomaly and risk values were computed.\n"
        "- **rag_explanation**: why protocol snippets were retrieved.\n"
        "- **referral_explanation**: why referral was or was not recommended.\n"
        "- **workflow_explanation**: end-to-end agentic reasoning summary."
    )

with tab_queue:
    st.subheader("Offline Sync Queue")
    st.code(adk.dump_queue(), language="json")
