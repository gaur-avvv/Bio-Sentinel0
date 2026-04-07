from __future__ import annotations

from src.models.inference_adapter import FallbackHeuristicBackend, get_inference_backend


def test_fallback_backend_extracts_respiratory_case() -> None:
    backend = FallbackHeuristicBackend()
    result = backend.extract("Patient has cough and breathlessness", "eng", {})
    assert result["syndrome"] == "acute_respiratory_infection"
    assert result["confidence"] > 0.0


def test_backend_factory_returns_usable_backend() -> None:
    backend = get_inference_backend(preferred="medgemma_gguf")
    caps = backend.get_capabilities()
    assert "backend" in caps
    result = backend.extract("fever for three days", "eng", {})
    assert "syndrome" in result or "error" in result
