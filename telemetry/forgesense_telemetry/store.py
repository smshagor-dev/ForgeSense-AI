from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
import threading
import time
from typing import Any

from forgesense_protocol import (
    HealthClass,
    MlObservation,
    SAFETY_COMM_TIMEOUT,
    SAFETY_EMERGENCY,
    SAFETY_HARD_CRITICAL,
    SAFETY_HARD_WARNING,
    SAFETY_ML_CRITICAL,
    SAFETY_ML_WARNING,
    SAFETY_SENSORS_VALID,
    SensorSnapshotWire,
    StatusSnapshotWire,
)

SCHEMA = "forgesense.telemetry.v1"
STATE_NAMES = {
    0: "STARTUP",
    1: "RUN",
    2: "WARNING",
    3: "SHUTDOWN",
    4: "FAULT_LATCHED",
    5: "RECOVERY",
}


@dataclass(frozen=True)
class TelemetryEvent:
    event_id: int
    host_monotonic_ms: int
    severity: str
    code: str
    message: str


@dataclass
class _Stamped:
    value: Any
    sequence: int
    source_timestamp_ms: int
    received_host_s: float


class TelemetryStore:
    """Thread-safe, read-only monitoring state assembled from validated data.

    The store does not expose actuator or recovery commands. FPGA status is the
    authoritative source for system state and output authority. ML observations
    remain a separate advisory/intelligence field.
    """

    def __init__(self, *, event_capacity: int = 256, stale_after_ms: int = 2000) -> None:
        if event_capacity < 1:
            raise ValueError("event_capacity must be positive")
        if stale_after_ms < 1:
            raise ValueError("stale_after_ms must be positive")
        self._lock = threading.RLock()
        self._changed = threading.Condition(self._lock)
        self._sensor: _Stamped | None = None
        self._status: _Stamped | None = None
        self._ml: _Stamped | None = None
        self._events: deque[TelemetryEvent] = deque(maxlen=event_capacity)
        self._next_event_id = 1
        self._revision = 0
        self.stale_after_ms = stale_after_ms

    @staticmethod
    def _host_ms() -> int:
        return int(time.monotonic() * 1000)

    def _append_event(self, severity: str, code: str, message: str) -> None:
        self._events.append(
            TelemetryEvent(
                event_id=self._next_event_id,
                host_monotonic_ms=self._host_ms(),
                severity=severity,
                code=code,
                message=message,
            )
        )
        self._next_event_id += 1

    def _commit_change(self) -> None:
        self._revision += 1
        self._changed.notify_all()

    def ingest_sensor(
        self,
        sensor: SensorSnapshotWire,
        *,
        sequence: int,
        source_timestamp_ms: int,
    ) -> None:
        with self._changed:
            previous_valid = self._sensor.value.all_valid if self._sensor is not None else None
            self._sensor = _Stamped(sensor, sequence, source_timestamp_ms, time.monotonic())
            if previous_valid is not None and previous_valid != sensor.all_valid:
                if sensor.all_valid:
                    self._append_event("info", "SENSORS_VALID", "Required sensor validity restored")
                else:
                    self._append_event("critical", "SENSOR_INVALID", "One or more required sensors became invalid")
            self._commit_change()

    def ingest_status(
        self,
        status: StatusSnapshotWire,
        *,
        sequence: int,
        source_timestamp_ms: int,
    ) -> None:
        with self._changed:
            previous = self._status.value if self._status is not None else None
            self._status = _Stamped(status, sequence, source_timestamp_ms, time.monotonic())
            if previous is None or previous.state_code != status.state_code:
                previous_name = STATE_NAMES.get(previous.state_code, "UNKNOWN") if previous else "NONE"
                current_name = STATE_NAMES.get(status.state_code, "UNKNOWN")
                severity = "critical" if status.state_code in (3, 4) else "warning" if status.state_code == 2 else "info"
                self._append_event(severity, "FPGA_STATE", f"FPGA state {previous_name} -> {current_name}")

            previous_flags = previous.safety_flags if previous is not None else 0
            rising = status.safety_flags & ~previous_flags
            for mask, code, message, severity in (
                (SAFETY_HARD_CRITICAL, "HARD_CRITICAL", "FPGA hard critical condition asserted", "critical"),
                (SAFETY_EMERGENCY, "EMERGENCY", "FPGA emergency input asserted", "critical"),
                (SAFETY_COMM_TIMEOUT, "COMM_TIMEOUT", "FPGA intelligence watchdog timed out", "critical"),
                (SAFETY_HARD_WARNING, "HARD_WARNING", "FPGA hard warning condition asserted", "warning"),
            ):
                if rising & mask:
                    self._append_event(severity, code, message)
            self._commit_change()

    def ingest_ml(
        self,
        observation: MlObservation,
        *,
        sequence: int,
        source_timestamp_ms: int,
    ) -> None:
        with self._changed:
            previous_health = self._ml.value.health_class if self._ml is not None else None
            self._ml = _Stamped(observation, sequence, source_timestamp_ms, time.monotonic())
            if previous_health != observation.health_class:
                name = HealthClass(observation.health_class).name
                severity = "critical" if observation.health_class == HealthClass.CRITICAL else "warning" if observation.health_class == HealthClass.WARNING else "info"
                self._append_event(severity, "ML_HEALTH", f"Edge intelligence class changed to {name}")
            self._commit_change()

    def _age_ms(self, stamped: _Stamped | None, now: float) -> int | None:
        if stamped is None:
            return None
        return max(0, int((now - stamped.received_host_s) * 1000))

    def _sensor_json(self, stamped: _Stamped | None, now: float) -> dict[str, Any] | None:
        if stamped is None:
            return None
        sensor: SensorSnapshotWire = stamped.value
        age = self._age_ms(stamped, now)
        return {
            "sequence": stamped.sequence,
            "source_timestamp_ms": stamped.source_timestamp_ms,
            "received_age_ms": age,
            "stale": age is not None and age > self.stale_after_ms,
            "temperature_c": sensor.temperature_c,
            "vibration_rms_g": sensor.vibration_rms_g,
            "current_a": sensor.current_a,
            "flags": sensor.flags,
            "all_valid": sensor.all_valid,
        }

    def _status_json(self, stamped: _Stamped | None, now: float) -> dict[str, Any] | None:
        if stamped is None:
            return None
        status: StatusSnapshotWire = stamped.value
        flags = status.safety_flags
        age = self._age_ms(stamped, now)
        return {
            "sequence": stamped.sequence,
            "source_timestamp_ms": stamped.source_timestamp_ms,
            "received_age_ms": age,
            "stale": age is not None and age > self.stale_after_ms,
            "state_code": status.state_code,
            "state": STATE_NAMES.get(status.state_code, "UNKNOWN"),
            "load_enable": status.load_enable,
            "warning_active": status.warning_active,
            "fault_latched": status.fault_latched,
            "operational_ready": status.operational_ready,
            "safety_flags": flags,
            "hard_warning": bool(flags & SAFETY_HARD_WARNING),
            "hard_critical": bool(flags & SAFETY_HARD_CRITICAL),
            "comm_timeout": bool(flags & SAFETY_COMM_TIMEOUT),
            "ml_warning": bool(flags & SAFETY_ML_WARNING),
            "ml_critical": bool(flags & SAFETY_ML_CRITICAL),
            "emergency": bool(flags & SAFETY_EMERGENCY),
            "sensors_valid": bool(flags & SAFETY_SENSORS_VALID),
        }

    def _ml_json(self, stamped: _Stamped | None, now: float) -> dict[str, Any] | None:
        if stamped is None:
            return None
        ml: MlObservation = stamped.value
        age = self._age_ms(stamped, now)
        return {
            "sequence": stamped.sequence,
            "source_timestamp_ms": stamped.source_timestamp_ms,
            "received_age_ms": age,
            "stale": age is not None and age > self.stale_after_ms,
            "model_id": ml.model_id,
            "model_version": ml.model_version,
            "feature_schema_version": ml.feature_schema_version,
            "anomaly_score": round(ml.anomaly_score, 6),
            "health_class": HealthClass(ml.health_class).name,
            "confidence": round(ml.confidence, 6),
            "inference_age_ms": ml.inference_age_ms,
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            sensor = self._sensor_json(self._sensor, now)
            status = self._status_json(self._status, now)
            ml = self._ml_json(self._ml, now)
            status_fresh = status is not None and not status["stale"]
            system_state = status["state"] if status_fresh else "UNKNOWN"
            return {
                "schema": SCHEMA,
                "revision": self._revision,
                "system": {
                    "state": system_state,
                    "authority": "fpga_status",
                    "monitoring_only": True,
                    "status_fresh": status_fresh,
                },
                "sensor": sensor,
                "fpga_status": status,
                "ml": ml,
            }

    def events(self, *, limit: int = 50) -> list[dict[str, Any]]:
        if not 1 <= limit <= 256:
            raise ValueError("limit must be in 1..256")
        with self._lock:
            return [asdict(event) for event in list(self._events)[-limit:]]

    def wait_for_revision(self, after: int, timeout_s: float = 15.0) -> int:
        with self._changed:
            if self._revision <= after:
                self._changed.wait(timeout=max(0.0, timeout_s))
            return self._revision
