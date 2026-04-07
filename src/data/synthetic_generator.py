from __future__ import annotations

from typing import Dict, List

from src.data.disease_definitions import WHO_IDSP_ALIGNED_SYNDROMES


def generate_synthetic_pairs(n: int = 100) -> List[Dict[str, object]]:
    """Generate simple synthetic encounter-to-structure pairs for bootstrapping."""
    syndrome_names = list(WHO_IDSP_ALIGNED_SYNDROMES.keys())
    pairs: List[Dict[str, object]] = []
    for idx in range(n):
        syndrome = syndrome_names[idx % len(syndrome_names)]
        defs = WHO_IDSP_ALIGNED_SYNDROMES[syndrome]
        pairs.append(
            {
                "input_text": f"Patient with likely {syndrome.replace('_', ' ')} for two days.",
                "target": {
                    "symptoms": [syndrome],
                    "syndrome_category": syndrome,
                    "severity": "moderate",
                    "onset_days": 2,
                    "idsp_flags": defs["reportable_flags"],
                    "icd10_codes": defs["icd10"],
                },
            }
        )
    return pairs
