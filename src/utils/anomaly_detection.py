from __future__ import annotations

from math import exp, factorial
from typing import Iterable


def poisson_pmf(k: int, lam: float) -> float:
    if k < 0:
        return 0.0
    return exp(-lam) * (lam**k) / factorial(k)


def poisson_tail_probability(k: int, lam: float, max_k: int = 100) -> float:
    if k <= 0:
        return 1.0
    cumulative = sum(poisson_pmf(i, lam) for i in range(k))
    return max(0.0, 1.0 - cumulative)


def cusum_score(values: Iterable[float], k: float = 0.5) -> float:
    running = 0.0
    best = 0.0
    for value in values:
        running = max(0.0, running + value - k)
        best = max(best, running)
    return best
