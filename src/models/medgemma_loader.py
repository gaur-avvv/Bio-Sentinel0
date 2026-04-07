from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LoadedModel:
    name: str
    device: str
    quantization: str


def load_medgemma_model(name: str, device: str, quantization: str) -> LoadedModel:
    """Return a lightweight model descriptor placeholder for local development."""
    return LoadedModel(name=name, device=device, quantization=quantization)
