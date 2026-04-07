from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
import json
import os


class InferenceBackend(ABC):
    @abstractmethod
    def extract(self, text: str, language: str, context: dict[str, Any]) -> dict[str, Any]:
        pass

    @abstractmethod
    def get_capabilities(self) -> dict[str, Any]:
        pass


class MedGemmaGGUFBackend(InferenceBackend):
    def __init__(self, model_path: str, n_gpu_layers: int = -1) -> None:
        self.available = False
        self.model = None
        try:
            from llama_cpp import Llama  # type: ignore

            self.model = Llama(
                model_path=model_path,
                n_ctx=4096,
                n_gpu_layers=n_gpu_layers if os.environ.get("ENABLE_GPU") else 0,
                verbose=False,
            )
            self.available = True
        except Exception:
            self.available = False

    def extract(self, text: str, language: str, context: dict[str, Any]) -> dict[str, Any]:
        if not self.available or self.model is None:
            return {"error": "backend_unavailable", "fallback": True}

        prompt = self._build_prompt(text=text, language=language, context=context)
        response = self.model(prompt, max_tokens=384, temperature=0.1, stop=["</s>", "```"])
        content = response["choices"][0]["text"].strip()
        try:
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content)
        except Exception:
            return {"error": "parse_failed", "raw": content}

    def _build_prompt(self, text: str, language: str, context: dict[str, Any]) -> str:
        return (
            "You are an India disease surveillance extractor. Return valid JSON only with keys: "
            "syndrome,severity,icd10_codes,symptoms,onset_days_ago,confidence,explanation.\n"
            f"Language={language}; district={context.get('district', 'unknown')}; note={text}"
        )

    def get_capabilities(self) -> dict[str, Any]:
        return {
            "backend": "medgemma_gguf",
            "offline": True,
            "languages": ["eng", "hin", "tam", "tel", "ben", "mar", "pan", "urd"],
            "modalities": ["text"],
            "available": self.available,
        }


class FallbackHeuristicBackend(InferenceBackend):
    def extract(self, text: str, language: str, context: dict[str, Any]) -> dict[str, Any]:
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["diarrhea", "diarrhoea", "dast", "loose motion"]):
            syndrome = "acute_watery_diarrhea"
            symptoms = ["diarrhea"]
            confidence = 0.72
            icd10 = ["A09"]
        elif any(kw in text_lower for kw in ["cough", "khansi", "breath", "saans"]):
            syndrome = "acute_respiratory_infection"
            symptoms = ["cough", "breathlessness"]
            confidence = 0.7
            icd10 = ["J06"]
        elif any(kw in text_lower for kw in ["rash", "spots", "daaney"]):
            syndrome = "acute_rash_with_fever"
            symptoms = ["rash", "fever"]
            confidence = 0.67
            icd10 = ["R21", "R50"]
        elif any(kw in text_lower for kw in ["seizure", "confusion", "fits", "stiff neck"]):
            syndrome = "acute_neurological_syndrome"
            symptoms = ["neurological_signs"]
            confidence = 0.66
            icd10 = ["G03"]
        elif any(kw in text_lower for kw in ["fever", "bukhar", "jwar"]):
            syndrome = "acute_febrile_illness"
            symptoms = ["fever"]
            confidence = 0.64
            icd10 = ["R50"]
        else:
            return {"syndrome": None, "confidence": 0.3, "error": "no_match"}

        return {
            "syndrome": syndrome,
            "severity": "moderate",
            "icd10_codes": icd10,
            "symptoms": symptoms,
            "onset_days_ago": None,
            "confidence": confidence,
            "explanation": "Heuristic keyword match",
        }

    def get_capabilities(self) -> dict[str, Any]:
        return {
            "backend": "heuristic_fallback",
            "offline": True,
            "languages": ["*"],
            "modalities": ["text"],
            "available": True,
        }


def get_inference_backend(preferred: str = "medgemma_gguf") -> InferenceBackend:
    backends: dict[str, callable] = {
        "medgemma_gguf": lambda: MedGemmaGGUFBackend(
            model_path=os.getenv("MEDGEMMA_PATH", "/models/medgemma-4b-indic-q4_k_m.gguf")
        ),
        "heuristic": lambda: FallbackHeuristicBackend(),
    }

    if preferred in backends:
        backend = backends[preferred]()
        caps = backend.get_capabilities()
        if caps.get("available", True):
            return backend

    return FallbackHeuristicBackend()
