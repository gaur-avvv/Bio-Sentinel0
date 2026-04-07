from __future__ import annotations

from statistics import mean
from typing import List


def simple_forecast(series: List[int], horizon: int = 3) -> List[float]:
    """Baseline mean forecast used as a deterministic placeholder."""
    if not series:
        return [0.0] * horizon
    avg = float(mean(series))
    return [avg for _ in range(horizon)]
