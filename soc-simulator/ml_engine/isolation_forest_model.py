"""Isolation Forest anomaly detector with joblib persistence."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from features import vectorize_batch


class IsolationForestDetector:
    def __init__(self) -> None:
        self.model = IsolationForest(
            contamination=0.1,
            random_state=42,
            n_estimators=100,
        )
        self._df_lo: float = -1.0
        self._df_hi: float = 1.0

    def train(self, log_dicts: Sequence[Mapping[str, Any]]) -> None:
        X = vectorize_batch(list(log_dicts))
        if len(X) == 0:
            return
        self.model.fit(X)
        df = self.model.decision_function(X)
        self._df_lo = float(np.min(df))
        self._df_hi = float(np.max(df))

    def score(self, log_dict: Mapping[str, Any]) -> float:
        """Anomaly score 0-10 (higher = more anomalous)."""
        X = vectorize_batch([log_dict])
        d = float(self.model.decision_function(X)[0])
        lo, hi = self._df_lo, self._df_hi
        span = hi - lo
        if span < 1e-9:
            return 5.0
        # sklearn IF: lower decision_function => more anomalous
        norm = (d - lo) / span
        norm = float(np.clip(norm, 0.0, 1.0))
        return float(10.0 * (1.0 - norm))

    def save(self, path: str) -> None:
        joblib.dump({"model": self.model, "df_lo": self._df_lo, "df_hi": self._df_hi}, path)

    def load(self, path: str) -> None:
        data = joblib.load(path)
        self.model = data["model"]
        self._df_lo = float(data.get("df_lo", -1.0))
        self._df_hi = float(data.get("df_hi", 1.0))
