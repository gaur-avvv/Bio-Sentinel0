from __future__ import annotations

from src.models.medsiglip_loader import encode_image


class ImageTriageAgent:
    def analyze(self, image_path: str) -> dict[str, float]:
        return encode_image(image_path)
