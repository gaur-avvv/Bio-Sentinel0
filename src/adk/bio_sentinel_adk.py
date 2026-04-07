from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

from src.adk.state import ClinicalEncounter
from src.adk.core import ADKRuntime, AgentSpec, Skill, Tool
from src.agents.api_integration_agent import IDSPSyncTool
from src.agents.alert_agent import AlertAgent
from src.agents.intake_agent import IntakeAgent
from src.agents.surveillance_agent import SurveillanceAgent
from src.models.inference_adapter import InferenceBackend, get_inference_backend


class BioSentinelADK:
    """Internal ADK-style runtime for orchestrating Bio Sentinel specialists."""

    def __init__(self, backend: InferenceBackend | None = None) -> None:
        self.intake_agent = IntakeAgent()
        self.surveillance_agent = SurveillanceAgent()
        self.alert_agent = AlertAgent()
        self.backend = backend or get_inference_backend(preferred="heuristic")
        self.idsp_sync = IDSPSyncTool()
        self.runtime = ADKRuntime()
        self.sync_queue: list[dict[str, Any]] = []
        self.protocol_corpus = self._load_protocol_corpus()
        self._register_tools()
        self._register_skills()
        self._register_agents()

    def _load_protocol_corpus(self) -> list[dict[str, str]]:
        default = [
            {
                "syndrome": "acute_watery_diarrhea",
                "source": "IDSP",
                "title": "Acute Diarrheal Disease Reporting",
                "content": "Notify district surveillance unit for unusual rise in watery diarrhea cases.",
            },
            {
                "syndrome": "acute_respiratory_infection",
                "source": "NHM",
                "title": "ARI Escalation Guidance",
                "content": "Escalate clusters with breathlessness and fever, especially in vulnerable groups.",
            },
            {
                "syndrome": "acute_febrile_illness",
                "source": "ICMR",
                "title": "Febrile Surveillance Baseline",
                "content": "Track fever clusters with local vector-borne disease context.",
            },
        ]
        guide_path = Path("docs/india_resource_guide.md")
        if not guide_path.exists():
            return default
        guide = guide_path.read_text(encoding="utf-8")
        return default + [
            {
                "syndrome": "generic",
                "source": "Bio Sentinel Resource Guide",
                "title": "India Resource Links",
                "content": guide[:1200],
            }
        ]

    def _register_tools(self) -> None:
        self.runtime.register_tool(
            Tool(
                name="extract_case",
                description="Extract a structured syndromic record from a clinical narrative.",
                handler=self._extract_case,
            )
        )
        self.runtime.register_tool(
            Tool(
                name="generate_fhir",
                description="Generate FHIR-like output from a structured record.",
                handler=self._generate_fhir,
            )
        )
        self.runtime.register_tool(
            Tool(
                name="analyze_batch",
                description="Aggregate and score a batch of records for outbreak risk.",
                handler=self._analyze_batch,
            )
        )
        self.runtime.register_tool(
            Tool(
                name="create_alert",
                description="Create escalation-ready alert content from a summary.",
                handler=self._create_alert,
            )
        )
        self.runtime.register_tool(
            Tool(
                name="retrieve_protocols",
                description="Retrieve offline protocol snippets for a syndrome and query.",
                handler=self._retrieve_protocols,
            )
        )
        self.runtime.register_tool(
            Tool(
                name="multimodal_fusion",
                description="Fuse text, audio, and image confidence signals.",
                handler=self._multimodal_fusion,
            )
        )
        self.runtime.register_tool(
            Tool(
                name="evaluate_uncertainty",
                description="Evaluate uncertainty and referral need from syndrome and confidence.",
                handler=self._evaluate_uncertainty,
            )
        )
        self.runtime.register_tool(
            Tool(
                name="sync_report",
                description="Simulate IDSP/IHIP sync with online/offline queue fallback.",
                handler=self._sync_report,
            )
        )

    def _register_skills(self) -> None:
        self.runtime.register_skill(
            Skill(
                name="triage_explanation",
                description="Explain how the intake decision was derived.",
                handler=self._triage_explanation,
            )
        )
        self.runtime.register_skill(
            Skill(
                name="risk_explanation",
                description="Explain surveillance risk scoring outputs.",
                handler=self._risk_explanation,
            )
        )
        self.runtime.register_skill(
            Skill(
                name="workflow_explanation",
                description="Explain full agent workflow and escalation logic.",
                handler=self._workflow_explanation,
            )
        )
        self.runtime.register_skill(
            Skill(
                name="rag_explanation",
                description="Explain why retrieved protocol evidence is relevant.",
                handler=self._rag_explanation,
            )
        )
        self.runtime.register_skill(
            Skill(
                name="referral_explanation",
                description="Explain referral recommendation from uncertainty evaluation.",
                handler=self._referral_explanation,
            )
        )

    def _register_agents(self) -> None:
        self.runtime.register_agent(
            AgentSpec(
                name="intake_specialist",
                role="Extracts structured syndromic data from frontline narratives.",
                tool_names=["extract_case", "generate_fhir"],
                skill_names=["triage_explanation"],
            )
        )
        self.runtime.register_agent(
            AgentSpec(
                name="surveillance_analyst",
                role="Aggregates signals and estimates outbreak risk.",
                tool_names=["analyze_batch"],
                skill_names=["risk_explanation"],
            )
        )
        self.runtime.register_agent(
            AgentSpec(
                name="escalation_coordinator",
                role="Produces escalation recommendations and advisories.",
                tool_names=["create_alert"],
                skill_names=["workflow_explanation"],
            )
        )
        self.runtime.register_agent(
            AgentSpec(
                name="medical_rag_agent",
                role="Retrieves guideline evidence from offline medical corpus.",
                tool_names=["retrieve_protocols"],
                skill_names=["rag_explanation"],
            )
        )
        self.runtime.register_agent(
            AgentSpec(
                name="multimodal_analyzer",
                role="Fuses text/audio/image confidence signals.",
                tool_names=["multimodal_fusion"],
                skill_names=[],
            )
        )
        self.runtime.register_agent(
            AgentSpec(
                name="uncertainty_evaluator",
                role="Determines referral requirements based on uncertainty rules.",
                tool_names=["evaluate_uncertainty"],
                skill_names=["referral_explanation"],
            )
        )
        self.runtime.register_agent(
            AgentSpec(
                name="api_integration_agent",
                role="Syncs or queues reports for IDSP/IHIP style integration.",
                tool_names=["sync_report"],
                skill_names=[],
            )
        )

    def _extract_case(self, text: str, state: str, district: str) -> dict[str, Any]:
        extraction = self.backend.extract(text=text, language="hin", context={"district": district, "state": state})
        baseline = self.intake_agent.extract_from_text(text=text, state=state, district=district)
        payload = baseline.model_dump(mode="json")

        if extraction.get("syndrome"):
            payload["syndrome_category"] = extraction.get("syndrome")
        if extraction.get("severity"):
            payload["severity"] = extraction.get("severity")
        if extraction.get("icd10_codes"):
            payload["icd10_codes"] = extraction.get("icd10_codes")
        if extraction.get("symptoms"):
            payload["symptoms"] = extraction.get("symptoms")
        if extraction.get("onset_days_ago") is not None:
            payload["onset_days"] = extraction.get("onset_days_ago")

        encounter = ClinicalEncounter(
            district=district,
            narrative_text=text,
            syndrome=payload.get("syndrome_category"),
            severity=payload.get("severity"),
            icd10_codes=payload.get("icd10_codes", []),
            symptoms=payload.get("symptoms", []),
            onset_days_ago=payload.get("onset_days"),
            confidence_score=float(extraction.get("confidence", 0.6)),
        )
        payload["encounter"] = encounter.model_dump(mode="json")
        payload["confidence_score"] = encounter.confidence_score
        payload["risk_tier"] = encounter.risk_tier
        return payload

    def _generate_fhir(self, record: dict[str, Any]) -> dict[str, Any]:
        # Re-constructing via intake pathway ensures stable schema for this baseline.
        required = ["symptoms", "syndrome_category", "patient_id"]
        for key in required:
            if key not in record:
                raise ValueError(f"Missing required record field for FHIR: {key}")
        synthetic_text = " ".join(record.get("symptoms", []))
        synthetic_record = self.intake_agent.extract_from_text(
            text=synthetic_text,
            state=record.get("location", {}).get("state", "Unknown"),
            district=record.get("location", {}).get("district", "Unknown"),
        )
        return self.alert_agent.to_fhir(synthetic_record)

    def _analyze_batch(self, events: list[dict[str, str]]) -> dict[str, Any]:
        records = [
            self.intake_agent.extract_from_text(
                text=event["text"],
                state=event["state"],
                district=event["district"],
            )
            for event in events
        ]
        summary = self.surveillance_agent.summarize(records)
        return {
            "records": [record.model_dump(mode="json") for record in records],
            "summary": summary,
        }

    def _create_alert(self, summary: dict[str, Any]) -> dict[str, Any]:
        return self.alert_agent.build_alert(summary)

    def _retrieve_protocols(self, query: str, syndrome: str, top_k: int = 3) -> list[dict[str, Any]]:
        query_l = query.lower()
        ranked: list[tuple[int, dict[str, str]]] = []
        for item in self.protocol_corpus:
            score = 0
            if item["syndrome"] in {syndrome, "generic"}:
                score += 2
            content_l = item["content"].lower()
            if syndrome.replace("_", " ") in content_l:
                score += 1
            if any(token in content_l for token in query_l.split()[:6]):
                score += 1
            ranked.append((score, item))
        ranked.sort(key=lambda x: x[0], reverse=True)
        selected = [
            {
                "source": item["source"],
                "title": item["title"],
                "content": item["content"][:280],
                "relevance_score": score,
            }
            for score, item in ranked[:top_k]
        ]
        return selected

    def _multimodal_fusion(
        self,
        text_conf: float,
        audio_conf: float = 0.0,
        image_conf: float = 0.0,
    ) -> dict[str, Any]:
        weights = {"text": 0.6, "audio": 0.25, "image": 0.15}
        fused = (
            weights["text"] * text_conf
            + weights["audio"] * audio_conf
            + weights["image"] * image_conf
        )
        if audio_conf > 0.7 and text_conf > 0.7:
            fused = min(0.99, fused * 1.1)
        elif abs(audio_conf - text_conf) > 0.4:
            fused *= 0.8
        return {
            "fused_confidence": round(max(0.0, min(1.0, fused)), 3),
            "modalities_used": {
                "text": text_conf > 0.3,
                "audio": audio_conf > 0.3,
                "image": image_conf > 0.3,
            },
        }

    def _evaluate_uncertainty(
        self,
        syndrome: str,
        severity: str,
        confidence_score: float,
    ) -> dict[str, Any]:
        min_conf = 0.6
        if syndrome in {"acute_neurological_syndrome", "acute_rash_with_fever"}:
            min_conf = 0.75
        needs_referral = False
        reasons: list[str] = []
        if confidence_score < min_conf:
            needs_referral = True
            reasons.append(f"Low confidence ({confidence_score:.2f} < {min_conf:.2f})")
        if severity == "severe" and confidence_score < 0.8:
            needs_referral = True
            reasons.append("Severe case with moderate confidence")
        return {
            "needs_referral": needs_referral,
            "referral_reason": "; ".join(reasons) if reasons else None,
            "confidence_score": round(confidence_score, 3),
        }

    def _sync_report(
        self,
        syndrome: str,
        severity: str,
        district: str,
        confidence_score: float,
        online: bool = False,
    ) -> dict[str, Any]:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "syndrome": syndrome,
            "severity": severity,
            "district": district,
            "confidence_score": confidence_score,
            "symptoms": [],
            "icd10_codes": [],
        }
        if online:
            result = self.idsp_sync(payload, force_sync=True)
            return result

        result = self.idsp_sync(payload, force_sync=False)
        if result.get("status") == "queued":
            self.sync_queue.append(payload)
        return result

    def _triage_explanation(self, record: dict[str, Any]) -> str:
        syndrome = record.get("syndrome_category", "unknown")
        symptoms = ", ".join(record.get("symptoms", []))
        onset_days = record.get("onset_days", "unknown")
        return (
            f"The Intake Specialist mapped the encounter to {syndrome} based on observed tokens "
            f"({symptoms}). It inferred onset as {onset_days} day(s) and attached IDSP-oriented flags "
            "for downstream surveillance."
        )

    def _risk_explanation(self, summary: dict[str, Any]) -> str:
        risk = summary.get("outbreak_risk_score", 0.0)
        counts = summary.get("syndrome_counts", {})
        return (
            "The Surveillance Analyst aggregated syndrome counts "
            f"{counts} and computed outbreak risk={risk}. "
            "Risk combines Poisson-aberration and CUSUM-trend components configured in surveillance YAML."
        )

    def _workflow_explanation(self, summary: dict[str, Any], alert: dict[str, Any]) -> str:
        return (
            "Workflow: Intake Specialist extracts structured records -> Surveillance Analyst computes "
            f"anomaly-aware summary (risk={summary.get('outbreak_risk_score', 0.0)}) -> Escalation Coordinator "
            f"assigns severity '{alert.get('severity', 'monitor')}' and action message."
        )

    def _rag_explanation(self, syndrome: str, protocols: list[dict[str, Any]]) -> str:
        sources = ", ".join({item.get("source", "unknown") for item in protocols})
        return (
            f"Medical RAG agent retrieved {len(protocols)} protocol snippets for {syndrome} "
            f"from sources: {sources}."
        )

    def _referral_explanation(self, uncertainty: dict[str, Any]) -> str:
        if uncertainty.get("needs_referral"):
            return (
                "Uncertainty Evaluator recommends referral due to: "
                f"{uncertainty.get('referral_reason', 'insufficient confidence')}"
            )
        return "Uncertainty Evaluator recommends no referral based on current confidence and severity."

    def run_single_pipeline(
        self,
        text: str,
        state: str,
        district: str,
        audio_conf: float = 0.0,
        image_conf: float = 0.0,
        online_sync: bool = False,
        collect_trace: bool = False,
    ) -> dict[str, Any]:
        trace: list[dict[str, Any]] = []
        record = self.runtime.run_tool(
            "intake_specialist",
            "extract_case",
            text=text,
            state=state,
            district=district,
        )
        if collect_trace:
            trace.append({"agent": "intake_specialist", "output": {"syndrome": record.get("syndrome_category"), "confidence": record.get("confidence_score")}})
        summary = self.runtime.run_tool(
            "surveillance_analyst",
            "analyze_batch",
            events=[{"text": text, "state": state, "district": district}],
        )["summary"]
        if collect_trace:
            trace.append({"agent": "surveillance_analyst", "output": {"risk": summary.get("outbreak_risk_score")}})
        text_conf = 1.0 - float(summary.get("outbreak_risk_score", 0.0))
        fusion = self.runtime.run_tool(
            "multimodal_analyzer",
            "multimodal_fusion",
            text_conf=text_conf,
            audio_conf=audio_conf,
            image_conf=image_conf,
        )
        protocols = self.runtime.run_tool(
            "medical_rag_agent",
            "retrieve_protocols",
            query=text,
            syndrome=record.get("syndrome_category", "acute_febrile_illness"),
            top_k=3,
        )
        if collect_trace:
            trace.append({"agent": "medical_rag_agent", "output": {"protocol_count": len(protocols)}})
        uncertainty = self.runtime.run_tool(
            "uncertainty_evaluator",
            "evaluate_uncertainty",
            syndrome=record.get("syndrome_category", "acute_febrile_illness"),
            severity=record.get("severity", "moderate"),
            confidence_score=fusion["fused_confidence"],
        )
        if collect_trace:
            trace.append({"agent": "uncertainty_evaluator", "output": uncertainty})
        alert = self.runtime.run_tool("escalation_coordinator", "create_alert", summary=summary)
        sync_status = self.runtime.run_tool(
            "api_integration_agent",
            "sync_report",
            syndrome=record.get("syndrome_category", "acute_febrile_illness"),
            severity=record.get("severity", "moderate"),
            district=district,
            confidence_score=fusion["fused_confidence"],
            online=online_sync,
        )
        if collect_trace:
            trace.append({"agent": "api_integration_agent", "output": sync_status})
        fhir = self.runtime.run_tool("intake_specialist", "generate_fhir", record=record)
        triage_note = self.runtime.run_skill("intake_specialist", "triage_explanation", record=record)
        risk_note = self.runtime.run_skill("surveillance_analyst", "risk_explanation", summary=summary)
        rag_note = self.runtime.run_skill(
            "medical_rag_agent",
            "rag_explanation",
            syndrome=record.get("syndrome_category", "acute_febrile_illness"),
            protocols=protocols,
        )
        referral_note = self.runtime.run_skill(
            "uncertainty_evaluator",
            "referral_explanation",
            uncertainty=uncertainty,
        )
        workflow_note = self.runtime.run_skill(
            "escalation_coordinator",
            "workflow_explanation",
            summary=summary,
            alert=alert,
        )
        result = {
            "record": record,
            "summary": summary,
            "alert": alert,
            "fhir": fhir,
            "protocols": protocols,
            "fusion": fusion,
            "uncertainty": uncertainty,
            "sync": sync_status,
            "explanations": {
                "triage": triage_note,
                "risk": risk_note,
                "rag": rag_note,
                "referral": referral_note,
                "workflow": workflow_note,
            },
        }
        if collect_trace:
            result["trace"] = trace
        return result

    def run_batch_pipeline(self, events: list[dict[str, str]], online_sync: bool = False) -> dict[str, Any]:
        analyzed = self.runtime.run_tool("surveillance_analyst", "analyze_batch", events=events)
        summary = analyzed["summary"]
        alert = self.runtime.run_tool("escalation_coordinator", "create_alert", summary=summary)
        dominant = max(summary.get("syndrome_counts", {"acute_febrile_illness": 0}), key=summary.get("syndrome_counts", {"acute_febrile_illness": 0}).get)
        protocols = self.runtime.run_tool(
            "medical_rag_agent",
            "retrieve_protocols",
            query="batch surveillance trends",
            syndrome=dominant,
            top_k=3,
        )
        uncertainty = self.runtime.run_tool(
            "uncertainty_evaluator",
            "evaluate_uncertainty",
            syndrome=dominant,
            severity="moderate",
            confidence_score=1.0 - float(summary.get("outbreak_risk_score", 0.0)),
        )
        sync_status = self.runtime.run_tool(
            "api_integration_agent",
            "sync_report",
            syndrome=dominant,
            severity="moderate",
            district=events[0].get("district", "unknown") if events else "unknown",
            confidence_score=1.0 - float(summary.get("outbreak_risk_score", 0.0)),
            online=online_sync,
        )
        risk_note = self.runtime.run_skill("surveillance_analyst", "risk_explanation", summary=summary)
        rag_note = self.runtime.run_skill(
            "medical_rag_agent",
            "rag_explanation",
            syndrome=dominant,
            protocols=protocols,
        )
        referral_note = self.runtime.run_skill(
            "uncertainty_evaluator",
            "referral_explanation",
            uncertainty=uncertainty,
        )
        workflow_note = self.runtime.run_skill(
            "escalation_coordinator",
            "workflow_explanation",
            summary=summary,
            alert=alert,
        )
        return {
            "records": analyzed["records"],
            "summary": summary,
            "alert": alert,
            "protocols": protocols,
            "uncertainty": uncertainty,
            "sync": sync_status,
            "explanations": {
                "risk": risk_note,
                "rag": rag_note,
                "referral": referral_note,
                "workflow": workflow_note,
            },
        }

    def list_agent_catalog(self) -> list[dict[str, Any]]:
        return self.runtime.list_agents()

    def export_graph_blueprint(self) -> dict[str, Any]:
        return {
            "nodes": [agent["name"] for agent in self.list_agent_catalog()],
            "edges": [
                ["intake_specialist", "medical_rag_agent"],
                ["medical_rag_agent", "multimodal_analyzer"],
                ["multimodal_analyzer", "uncertainty_evaluator"],
                ["uncertainty_evaluator", "surveillance_analyst"],
                ["surveillance_analyst", "escalation_coordinator"],
                ["escalation_coordinator", "api_integration_agent"],
            ],
        }

    def dump_queue(self) -> str:
        return json.dumps(self.sync_queue, indent=2)
