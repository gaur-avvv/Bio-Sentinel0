from __future__ import annotations

from collections import Counter
from typing import Iterable

from src.data.syndromic_schema import SyndromicRecord
from src.models.forecaster import simple_forecast
from src.utils.anomaly_detection import cusum_score, poisson_tail_probability
from src.utils.config_loader import load_yaml_config


class SurveillanceAgent:
    def __init__(self, config_path: str = "configs/surveillance_config.yaml") -> None:
        self.config = load_yaml_config(config_path)

    def _thresholds_for(self, syndrome: str) -> tuple[float, float]:
        thresholds = self.config.get("thresholds", {})
        syndrome_cfg = thresholds.get(syndrome, {}) if isinstance(thresholds, dict) else {}
        lam = float(syndrome_cfg.get("poisson_lambda", 5))
        cusum_k = float(syndrome_cfg.get("cusum_k", 0.5))
        return lam, cusum_k

    def summarize(self, records: Iterable[SyndromicRecord]) -> dict:
        records = list(records)
        syndrome_counts = Counter(r.syndrome_category for r in records)
        series = list(syndrome_counts.values())
        risk = 0.0
        anomaly_details: dict[str, dict[str, float]] = {}

        for syndrome, count in syndrome_counts.items():
            lam, k = self._thresholds_for(syndrome)
            poisson_risk = 1.0 - poisson_tail_probability(count, lam=lam)
            cusum_component = min(0.3, cusum_score([float(count)], k=k) / 10.0)
            syndrome_risk = min(1.0, max(0.0, poisson_risk + cusum_component))
            anomaly_details[syndrome] = {
                "count": float(count),
                "poisson_lambda": lam,
                "poisson_component": round(poisson_risk, 3),
                "cusum_component": round(cusum_component, 3),
                "syndrome_risk": round(syndrome_risk, 3),
            }
            risk = max(risk, syndrome_risk)

        if series:
            trend_component = min(0.2, cusum_score([float(x) for x in series], k=0.5) / 15.0)
            risk = min(1.0, risk + trend_component)

        return {
            "total_records": len(records),
            "syndrome_counts": dict(syndrome_counts),
            "anomaly_details": anomaly_details,
            "forecast": simple_forecast(series, horizon=3),
            "outbreak_risk_score": round(risk, 3),
        }
