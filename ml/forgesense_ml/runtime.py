from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from statistics import fmean

from forgesense_protocol import HealthClass as ProtocolHealthClass
from forgesense_protocol import MlObservation, VALID_OBSERVATION

from .baseline import DiagonalGaussianModel


@dataclass(frozen=True)
class FeatureWindowConfig:
    size: int = 8
    invalid_resets_window: bool = True


class FeatureWindow:
    """Small deterministic feature window for the first edge runtime."""

    def __init__(self, config: FeatureWindowConfig = FeatureWindowConfig()) -> None:
        if config.size < 2:
            raise ValueError("feature window size must be at least 2")
        self.config = config
        self._rows: deque[tuple[float, float, float]] = deque(maxlen=config.size)

    @property
    def ready(self) -> bool:
        return len(self._rows) == self.config.size

    def clear(self) -> None:
        self._rows.clear()

    def ingest(self, snapshot) -> bool:
        if not snapshot.all_valid:
            if self.config.invalid_resets_window:
                self.clear()
            return False
        self._rows.append(snapshot.feature_vector())
        return self.ready

    def vector(self) -> tuple[float, float, float]:
        if not self.ready:
            raise RuntimeError("feature window not ready")
        columns = list(zip(*self._rows))
        values = tuple(fmean(column) for column in columns)
        return values[0], values[1], values[2]


class EdgeInferenceRuntime:
    """Converts validated sensor windows into bounded protocol observations."""

    def __init__(self, model: DiagonalGaussianModel, *, window_size: int = 8) -> None:
        self.model = model
        self.window = FeatureWindow(FeatureWindowConfig(window_size))

    def ingest(self, snapshot) -> MlObservation | None:
        if not self.window.ingest(snapshot):
            return None
        result = self.model.infer(self.window.vector())
        return MlObservation(
            model_id=self.model.model_id,
            model_version=self.model.model_version,
            feature_schema_version=self.model.feature_schema_version,
            flags=VALID_OBSERVATION,
            anomaly_score=result.anomaly_score,
            health_class=ProtocolHealthClass(int(result.health_class)),
            confidence=result.confidence,
            inference_age_ms=0,
        )
