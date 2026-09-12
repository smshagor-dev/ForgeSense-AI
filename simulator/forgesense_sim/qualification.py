from __future__ import annotations

from dataclasses import asdict
from typing import Any

from forgesense_ml.reference import STARTUP_SETTLE_SAMPLES, fit_reference_model
from forgesense_ml.runtime import EdgeInferenceRuntime
from forgesense_protocol import encode_ml_observation

from .closed_loop import SafetyControllerModel, SafetyState
from .plant import ChannelImpairment, MachinePlant, SensorImpairmentProfile
from .validation import run_validation_matrix

QUALIFICATION_SCHEMA = "forgesense.software_qualification.v1"


def _run_normal_soak(seed: int, samples: int = 400) -> dict[str, Any]:
    """Exercise the declared normal envelope with an independent noise seed.

    The load schedule intentionally matches the canonical normal scenario. Broader
    operating-regime shifts are tested separately so this stability check cannot
    accidentally redefine the model's declared normal envelope.
    """

    model = fit_reference_model()
    runtime = EdgeInferenceRuntime(model, window_size=8)
    controller = SafetyControllerModel(watchdog_timeout_steps=15)
    plant = MachinePlant(seed=seed)
    sequence = 0
    terminal: str | None = None
    accepted = 0
    warnings = 0
    for index in range(samples):
        load = 0.56 + 0.15 * ((index // 60) % 3) / 2.0
        machine = plant.step(load=load, dt_s=0.1)
        snapshot = plant.sense(machine)
        observation = runtime.ingest(snapshot)
        ready = index >= STARTUP_SETTLE_SAMPLES and observation is not None
        frame = None
        if ready:
            frame = encode_ml_observation(
                observation,
                sequence=sequence,
                timestamp_ms=int(snapshot.time_s * 1000) & 0xFFFFFFFF,
            )
            sequence = (sequence + 1) & 0xFFFF
        output = controller.step(snapshot, startup_done=ready, ml_frame=frame)
        accepted += int(output.accepted_ml)
        warnings += int(output.state is SafetyState.WARNING)
        if output.state in (SafetyState.SHUTDOWN, SafetyState.FAULT_LATCHED):
            terminal = output.state.name
            break
    return {
        "seed": seed,
        "requested_samples": samples,
        "accepted_ml_frames": accepted,
        "warning_steps": warnings,
        "terminal_state": terminal,
        "passed": terminal is None,
    }


def _run_replay_abuse() -> dict[str, Any]:
    model = fit_reference_model()
    runtime = EdgeInferenceRuntime(model, window_size=8)
    controller = SafetyControllerModel(watchdog_timeout_steps=5)
    plant = MachinePlant(seed=11)
    snapshots = []
    observation = None
    for _ in range(120):
        machine = plant.step(load=0.56, dt_s=0.1)
        snapshot = plant.sense(machine)
        snapshots.append(snapshot)
        observation = runtime.ingest(snapshot)
    if observation is None:
        raise RuntimeError("qualification could not produce an ML observation")
    frame = encode_ml_observation(observation, sequence=1, timestamp_ms=12000)
    first = controller.step(snapshots[-1], startup_done=True, ml_frame=frame)
    rejected = 0
    final = first
    for _ in range(controller.watchdog_timeout_steps):
        final = controller.step(snapshots[-1], startup_done=True, ml_frame=frame)
        rejected += int(not final.accepted_ml)
        if final.state is SafetyState.SHUTDOWN:
            break
    return {
        "first_frame_accepted": first.accepted_ml,
        "replayed_frames_rejected": rejected,
        "terminal_state": final.state.name,
        "passed": first.accepted_ml and rejected >= 1 and final.state is SafetyState.SHUTDOWN,
    }


def _run_reset_and_sensor_fail_closed() -> dict[str, Any]:
    model = fit_reference_model()
    runtime = EdgeInferenceRuntime(model, window_size=8)
    controller = SafetyControllerModel(watchdog_timeout_steps=10)
    plant = MachinePlant(seed=3)
    last_snapshot = None
    for index in range(100):
        machine = plant.step(load=0.56, dt_s=0.1)
        last_snapshot = plant.sense(machine)
        observation = runtime.ingest(last_snapshot)
        if observation is not None and index >= STARTUP_SETTLE_SAMPLES:
            frame = encode_ml_observation(observation, sequence=index & 0xFFFF, timestamp_ms=index * 100)
            controller.step(last_snapshot, startup_done=True, ml_frame=frame)
    if last_snapshot is None:
        raise RuntimeError("qualification produced no sensor sample")
    controller.reset()
    after_reset = controller.step(last_snapshot, startup_done=False, ml_frame=None)

    machine = plant.step(load=0.56, dt_s=0.1)
    invalid = plant.sense(
        machine,
        impairments=SensorImpairmentProfile(current=ChannelImpairment(noise_sigma=0.0, dropout=True)),
    )
    invalid_result = controller.step(invalid, startup_done=True, ml_frame=None)
    return {
        "reset_load_enable": after_reset.load_enable,
        "reset_state": after_reset.state.name,
        "sensor_dropout_state": invalid_result.state.name,
        "sensor_dropout_hard_critical": invalid_result.hard_critical,
        "passed": (
            after_reset.load_enable is False
            and after_reset.state is SafetyState.STARTUP
            and invalid_result.state is SafetyState.FAULT_LATCHED
            and invalid_result.hard_critical
        ),
    }


def _run_shift_hard_limit() -> dict[str, Any]:
    plant = MachinePlant(seed=5)
    controller = SafetyControllerModel()
    machine = plant.step(load=0.6, dt_s=0.1)
    shifted = plant.sense(
        machine,
        impairments=SensorImpairmentProfile(
            current=ChannelImpairment(noise_sigma=0.0, stuck_value=4.0)
        ),
    )
    output = controller.step(shifted, startup_done=True, ml_frame=None)
    return {
        "current_a": shifted.current_a,
        "state": output.state.name,
        "hard_critical": output.hard_critical,
        "passed": output.state is SafetyState.FAULT_LATCHED and output.hard_critical,
    }


def run_software_qualification() -> dict[str, Any]:
    matrix = run_validation_matrix()
    normal_stability = [_run_normal_soak(seed) for seed in (7, 17, 29)]
    replay = _run_replay_abuse()
    reset = _run_reset_and_sensor_fail_closed()
    shift = _run_shift_hard_limit()
    checks = {
        "validation_matrix": all(item.passed for item in matrix),
        "normal_multi_seed_stability": all(item["passed"] for item in normal_stability),
        "replay_abuse": replay["passed"],
        "reset_and_sensor_fail_closed": reset["passed"],
        "dataset_shift_hard_limit": shift["passed"],
    }
    return {
        "schema": QUALIFICATION_SCHEMA,
        "virtual_only": True,
        "passed": all(checks.values()),
        "checks": checks,
        "validation_matrix": [
            {
                **asdict(item),
                "terminal_state": item.terminal_state.name if item.terminal_state is not None else None,
            }
            for item in matrix
        ],
        "normal_multi_seed_stability": normal_stability,
        "communication_replay_abuse": replay,
        "reset_and_sensor_fail_closed": reset,
        "dataset_shift_hard_limit": shift,
        "evidence_boundary": (
            "This is deterministic software qualification only. It is not a physical soak, brownout, EMC, "
            "latency, memory, thermal, or reliability result."
        ),
    }
