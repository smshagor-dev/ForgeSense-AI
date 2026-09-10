from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import json
import math
from pathlib import Path
from statistics import fmean, pstdev
from typing import Iterable, Sequence


class HealthClass(IntEnum):
    NORMAL = 0
    WARNING = 1
    CRITICAL = 2


@dataclass(frozen=True)
class InferenceResult:
    anomaly_score: float
    health_class: HealthClass
    confidence: float
    squared_z_mean: float


@dataclass(frozen=True)
class DiagonalGaussianModel:
    model_id: int
    model_version: int
    feature_schema_version: int
    feature_names: tuple[str, ...]
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    warning_threshold: float = 0.72
    critical_threshold: float = 0.90

    @classmethod
    def fit(cls, rows: Iterable[Sequence[float]], *, model_id: int = 1, model_version: int = 1, feature_schema_version: int = 1, feature_names: Sequence[str] = ("temperature_c", "vibration_rms_g", "current_a")) -> "DiagonalGaussianModel":
        data = [tuple(float(x) for x in row) for row in rows]
        if len(data) < 20:
            raise ValueError("at least 20 valid baseline samples are required")
        width = len(data[0])
        if width != len(feature_names) or any(len(row) != width for row in data):
            raise ValueError("feature width mismatch")
        columns = list(zip(*data))
        mean = tuple(fmean(col) for col in columns)
        scale = tuple(max(pstdev(col), 1e-4) for col in columns)
        return cls(model_id, model_version, feature_schema_version, tuple(feature_names), mean, scale)

    def infer(self, row: Sequence[float]) -> InferenceResult:
        if len(row) != len(self.mean):
            raise ValueError("feature width mismatch")
        z2 = [((float(value) - mu) / sigma) ** 2 for value, mu, sigma in zip(row, self.mean, self.scale)]
        squared_z_mean = fmean(z2)
        score = min(max(1.0 - math.exp(-0.5 * squared_z_mean), 0.0), 1.0)
        if score >= self.critical_threshold:
            health = HealthClass.CRITICAL
        elif score >= self.warning_threshold:
            health = HealthClass.WARNING
        else:
            health = HealthClass.NORMAL
        distance_from_boundary = min(abs(score - self.warning_threshold), abs(score - self.critical_threshold))
        confidence = min(0.5 + distance_from_boundary, 0.99)
        return InferenceResult(score, health, confidence, squared_z_mean)

    def to_dict(self) -> dict:
        return {
            "format": "forgesense.diag-gaussian.v1",
            "model_id": self.model_id,
            "model_version": self.model_version,
            "feature_schema_version": self.feature_schema_version,
            "feature_names": list(self.feature_names),
            "mean": list(self.mean),
            "scale": list(self.scale),
            "warning_threshold": self.warning_threshold,
            "critical_threshold": self.critical_threshold,
        }

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
