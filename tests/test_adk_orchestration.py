from __future__ import annotations

from src.adk import BioSentinelADK


def test_adk_catalog_has_expected_agents() -> None:
    adk = BioSentinelADK()
    catalog = adk.list_agent_catalog()
    names = {agent["name"] for agent in catalog}
    assert {
        "intake_specialist",
        "surveillance_analyst",
        "escalation_coordinator",
        "medical_rag_agent",
        "multimodal_analyzer",
        "uncertainty_evaluator",
        "api_integration_agent",
    }.issubset(names)


def test_adk_single_pipeline_outputs_explanations() -> None:
    adk = BioSentinelADK()
    result = adk.run_single_pipeline(
        text="Patient ko bukhar aur khansi hai 3 din se",
        state="Uttar Pradesh",
        district="Lucknow",
        audio_conf=0.6,
        image_conf=0.3,
        online_sync=False,
        collect_trace=True,
    )
    assert result["summary"]["total_records"] == 1
    assert "workflow" in result["explanations"]
    assert "rag" in result["explanations"]
    assert "referral" in result["explanations"]
    assert "protocols" in result and isinstance(result["protocols"], list)
    assert "uncertainty" in result and "needs_referral" in result["uncertainty"]
    assert "sync" in result and result["sync"]["status"] in {"pending", "success", "queued"}
    assert "trace" in result and isinstance(result["trace"], list)
    assert result["alert"]["severity"] in {"monitor", "district_alert", "state_escalation"}


def test_adk_batch_pipeline_and_graph_blueprint() -> None:
    adk = BioSentinelADK()
    events = [
        {"text": "Watery diarrhea for 2 days", "state": "Bihar", "district": "Patna"},
        {"text": "Khansi aur bukhar 3 din se", "state": "UP", "district": "Lucknow"},
    ]
    result = adk.run_batch_pipeline(events, online_sync=False)
    graph = adk.export_graph_blueprint()
    assert result["summary"]["total_records"] == 2
    assert "nodes" in graph and "edges" in graph
    assert isinstance(graph["nodes"], list)
