from __future__ import annotations

from dataclasses import dataclass
import random


@dataclass(frozen=True)
class FaultProfile:
    bearing: float = 0.0
    overcurrent: float = 0.0
    cooling_loss: float = 0.0

    def clamped(self) -> "FaultProfile":
        return FaultProfile(
            bearing=min(max(self.bearing, 0.0), 1.0),
            overcurrent=min(max(self.overcurrent, 0.0), 1.0),
            cooling_loss=min(max(self.cooling_loss, 0.0), 1.0),
        )


@dataclass(frozen=True)
class MachineSample:
    sample_index: int
    time_s: float
    load: float
    temperature_c: float
    vibration_rms_g: float
    current_a: float
    speed_rpm: float
    fault: FaultProfile


@dataclass(frozen=True)
class SensorSnapshot:
    sample_index: int
    time_s: float
    temperature_c: float
    vibration_rms_g: float
    current_a: float
    valid_temperature: bool = True
    valid_vibration: bool = True
    valid_current: bool = True

    @property
    def all_valid(self) -> bool:
        return self.valid_temperature and self.valid_vibration and self.valid_current

    def feature_vector(self) -> tuple[float, float, float]:
        if not self.all_valid:
            raise ValueError("invalid sensor snapshot cannot be converted to an ML feature vector")
        return self.temperature_c, self.vibration_rms_g, self.current_a


class MachinePlant:
    """Deterministic pre-hardware electromechanical reference plant."""

    def __init__(self, *, ambient_c: float = 24.0, seed: int = 1) -> None:
        self.ambient_c = ambient_c
        self.temperature_c = ambient_c
        self.vibration_rms_g = 0.04
        self.current_a = 0.0
        self.speed_rpm = 0.0
        self._rng = random.Random(seed)
        self._sample_index = 0
        self._time_s = 0.0

    def step(self, *, load: float, dt_s: float, fault: FaultProfile | None = None) -> MachineSample:
        if dt_s <= 0:
            raise ValueError("dt_s must be positive")
        load = min(max(load, 0.0), 1.0)
        f = (fault or FaultProfile()).clamped()
        target_current = 0.08 + 2.15 * load + 0.80 * f.overcurrent + 0.55 * load * f.bearing
        self.current_a += (target_current - self.current_a) * min(dt_s / 0.35, 1.0)
        target_vibration = 0.035 + 0.16 * load + 0.95 * f.bearing
        self.vibration_rms_g += (target_vibration - self.vibration_rms_g) * min(dt_s / 0.25, 1.0)
        thermal_rise = 5.2 * self.current_a * self.current_a + 20.0 * f.cooling_loss
        target_temp = self.ambient_c + thermal_rise
        thermal_tau = 42.0 * (1.0 + 1.8 * f.cooling_loss)
        self.temperature_c += (target_temp - self.temperature_c) * min(dt_s / thermal_tau, 1.0)
        speed_target = 3200.0 * load * (1.0 - 0.22 * f.bearing)
        self.speed_rpm += (speed_target - self.speed_rpm) * min(dt_s / 0.30, 1.0)
        sample = MachineSample(self._sample_index, self._time_s, load, self.temperature_c, self.vibration_rms_g, self.current_a, self.speed_rpm, f)
        self._sample_index += 1
        self._time_s += dt_s
        return sample

    def sense(self, sample: MachineSample, *, dropout_temperature: bool = False, dropout_vibration: bool = False, dropout_current: bool = False) -> SensorSnapshot:
        def noisy(value: float, sigma: float) -> float:
            return value + self._rng.gauss(0.0, sigma)
        return SensorSnapshot(
            sample_index=sample.sample_index,
            time_s=sample.time_s,
            temperature_c=noisy(sample.temperature_c, 0.04),
            vibration_rms_g=max(0.0, noisy(sample.vibration_rms_g, 0.004)),
            current_a=max(0.0, noisy(sample.current_a, 0.008)),
            valid_temperature=not dropout_temperature,
            valid_vibration=not dropout_vibration,
            valid_current=not dropout_current,
        )
