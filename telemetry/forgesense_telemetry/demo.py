from __future__ import annotations

import threading
import time

from forgesense_ml.reference import fit_reference_model
from forgesense_ml.runtime import EdgeInferenceRuntime
from forgesense_protocol import (
    SAFETY_HARD_CRITICAL,
    SAFETY_HARD_WARNING,
    SAFETY_ML_CRITICAL,
    SAFETY_ML_WARNING,
    SAFETY_SENSORS_VALID,
    SENSOR_ALL_VALID,
    MlObservation,
    SensorSnapshotWire,
    StatusSnapshotWire,
    encode_ml_observation,
)
from forgesense_sim import SafetyControllerModel, SafetyState, build_scenario, run_scenario

from .store import TelemetryStore


def _sensor_wire(sample) -> SensorSnapshotWire:
    flags = SENSOR_ALL_VALID if sample.all_valid else 0
    return SensorSnapshotWire(
        temperature_deci_c=round(sample.temperature_c * 10),
        vibration_milli_g=max(0, round(sample.vibration_rms_g * 1000)),
        current_milli_a=max(0, round(sample.current_a * 1000)),
        flags=flags,
    )


def _status_wire(output, *, ready: bool, ml: MlObservation | None, sensors_valid: bool) -> StatusSnapshotWire:
    control = 0
    control |= 0x01 if output.load_enable else 0
    control |= 0x02 if output.warning_active else 0
    control |= 0x04 if output.fault_latched else 0
    control |= 0x08 if ready else 0
    safety = 0
    safety |= SAFETY_HARD_WARNING if output.hard_warning else 0
    safety |= SAFETY_HARD_CRITICAL if output.hard_critical else 0
    safety |= SAFETY_ML_WARNING if ml is not None and int(ml.health_class) == 1 else 0
    safety |= SAFETY_ML_CRITICAL if ml is not None and int(ml.health_class) == 2 else 0
    safety |= SAFETY_SENSORS_VALID if sensors_valid else 0
    return StatusSnapshotWire(int(output.state), control, safety)


def start_demo_publisher(
    store: TelemetryStore,
    *,
    scenario_name: str = "bearing_degradation",
    interval_s: float = 0.08,
) -> threading.Thread:
    if interval_s <= 0:
        raise ValueError("interval_s must be positive")

    def run() -> None:
        samples = run_scenario(build_scenario(scenario_name))
        runtime = EdgeInferenceRuntime(fit_reference_model(), window_size=8)
        controller = SafetyControllerModel(watchdog_timeout_steps=15)
        ml_sequence = 0
        status_sequence = 0
        ready = False
        for sample in samples:
            sensor = _sensor_wire(sample)
            source_ms = int(sample.time_s * 1000) & 0xFFFFFFFF
            store.ingest_sensor(sensor, sequence=sample.sample_index & 0xFFFF, source_timestamp_ms=source_ms)
            observation = runtime.ingest(sensor)
            if sample.sample_index >= 80 and observation is not None:
                ready = True
                store.ingest_ml(observation, sequence=ml_sequence, source_timestamp_ms=source_ms)
                ml_sequence = (ml_sequence + 1) & 0xFFFF
            ml_frame = None
            if ready and observation is not None:
                ml_frame = encode_ml_observation(
                    observation,
                    sequence=(ml_sequence - 1) & 0xFFFF,
                    timestamp_ms=source_ms,
                )
            output = controller.step(sample, startup_done=ready, ml_frame=ml_frame)
            # The dashboard demo is monitoring-only. It mirrors the software oracle's
            # deterministic state but never sends commands back into the controller.
            status = _status_wire(output, ready=ready, ml=observation, sensors_valid=sample.all_valid)
            store.ingest_status(status, sequence=status_sequence, source_timestamp_ms=source_ms)
            status_sequence = (status_sequence + 1) & 0xFFFF
            if output.state in (SafetyState.SHUTDOWN, SafetyState.FAULT_LATCHED):
                # Keep terminal state visible briefly in accelerated demo mode.
                time.sleep(interval_s * 4)
                break
            time.sleep(interval_s)

    thread = threading.Thread(target=run, name="forgesense-demo-publisher", daemon=True)
    thread.start()
    return thread
