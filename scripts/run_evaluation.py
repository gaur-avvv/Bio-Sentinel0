from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.agents.intake_agent import IntakeAgent


SAMPLES = [
    "Patient has fever and cough for 3 days",
    "Patient reports watery diarrhea since yesterday",
]


def main() -> None:
    agent = IntakeAgent()
    for sample in SAMPLES:
        record = agent.extract_from_text(sample, state="Karnataka", district="Mysuru")
        print(record.model_dump())


if __name__ == "__main__":
    main()
