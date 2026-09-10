from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from forgesense_protocol import FreshnessGate, HealthClass
from forgesense_protocol import decode_frame, decode_ml_observation, encode_ml_observation


class SafetyState(IntEnum):
    STARTUP = 0
    RUN = 1
    WARNING = 2
    SHUTDOWN = 3
    FAULT_LATCHED = 4
    RECOVERY = 5


@dataclass(frozen=True)
class SafetyThresholds:
    temp_warn_c: float = 65.0
    temp_crit_c: float = 80.0
    vibration_warn_g: float = 0.600
    vibration_crit_g: float = 1.000
    current_warn_a: float = 2.500
    current_crit_a: float = 3.200


@dataclass(frozen=True)
class ControllerOutput:
    state: SafetyState
    load_enable: bool
    warning_active: bool
    fault_latched: bool
    hard_warning: bool
    hard_critical: bool
    accepted_ml: bool
    rejection_reason: str | None


class SafetyControllerModel:
    """Cycle-level software oracle mirroring the FPGA safety authority."""

    def __init__(
        self,
        *,
        thresholds: SafetyThresholds = SafetyThresholds(),
        watchdog_timeout_steps: int = 20,
    ) -> None:
        if watchdog_timeout_steps < 1:
            raise ValueError("watchdog_timeout_steps must be positive")
        self.thresholds = thresholds
        self.watchdog_timeout_steps = watchdog_timeout_steps
        self.state = SafetyState.STARTUP
        self.latched = False
        self._steps_since_kick = 0
        self.gate = FreshnessGate(1, 1, 1)

    def reset(self) -> None:
        self.state = SafetyState.STARTUP
        self.latched = False
        self._steps_since_kick = 0
        self.gate.last_sequence = None

    def _hard_limits(self, snapshot) -> tuple[bool, bool]:
        if not snapshot.all_valid:
            return False, True
        limits = self.thresholds
        critical = (
            snapshot.temperature_c >= limits.temp_crit_c
            or snapshot.vibration_rms_g >= limits.vibration_crit_g
            or snapshot.current_a >= limits.current_crit_a
        )
        warning = (not critical) and (
            snapshot.temperature_c >= limits.temp_warn_c
            or snapshot.vibration_rms_g >= limits.vibration_warn_g
            or snapshot.current_a >= limits.current_warn_a
        )
        return warning, critical

    def step(
        self,
        snapshot,
        *,
        startup_done: bool = True,
        emergency: bool = False,
        ml_frame: bytes | None = None,
        recovery_req: bool = False,
    ) -> ControllerOutput:
        hard_warning, hard_critical = self._hard_limits(snapshot)
        ml_valid = False
        ml_warning = False
        ml_critical = False
        reason = None

        if ml_frame is not None:
            try:
                frame = decode_frame(ml_frame)
                observation = decode_ml_observation(frame)
                ml_valid, reason = self.gate.accept(frame, observation)
                if ml_valid:
                    ml_warning = observation.health_class is HealthClass.WARNING
                    ml_critical = observation.health_class is HealthClass.CRITICAL
            except ValueError as exc:
                reason = str(exc)

        if not startup_done:
            self._steps_since_kick = 0
            comm_timeout = False
        elif ml_valid:
            self._steps_since_kick = 0
            comm_timeout = False
        else:
            self._steps_since_kick += 1
            comm_timeout = self._steps_since_kick >= self.watchdog_timeout_steps

        if emergency or hard_critical:
            self.state = SafetyState.FAULT_LATCHED
            self.latched = True
        elif self.state is SafetyState.STARTUP:
            if comm_timeout:
                self.state = SafetyState.SHUTDOWN
            elif startup_done:
                self.state = SafetyState.RUN
        elif self.state is SafetyState.RUN:
            if comm_timeout or (ml_valid and ml_critical):
                self.state = SafetyState.SHUTDOWN
            elif hard_warning or (ml_valid and ml_warning):
                self.state = SafetyState.WARNING
        elif self.state is SafetyState.WARNING:
            if comm_timeout or (ml_valid and ml_critical):
                self.state = SafetyState.SHUTDOWN
            elif not hard_warning and (not ml_valid or not ml_warning):
                self.state = SafetyState.RUN
        elif self.state is SafetyState.SHUTDOWN:
            if recovery_req and not comm_timeout and not hard_warning and not hard_critical:
                self.state = SafetyState.RECOVERY
        elif self.state is SafetyState.FAULT_LATCHED:
            if recovery_req and not emergency and not hard_critical:
                self.latched = False
                self.state = SafetyState.RECOVERY
        elif self.state is SafetyState.RECOVERY:
            self.state = SafetyState.STARTUP

        return ControllerOutput(
            state=self.state,
            load_enable=self.state in (SafetyState.RUN, SafetyState.WARNING),
            warning_active=self.state is SafetyState.WARNING,
            fault_latched=self.latched,
            hard_warning=hard_warning,
            hard_critical=hard_critical,
            accepted_ml=ml_valid,
            rejection_reason=reason,
        )


def encode_runtime_observation(observation, *, sequence: int, timestamp_ms: int) -> bytes:
    return encode_ml_observation(observation, sequence=sequence, timestamp_ms=timestamp_ms)
