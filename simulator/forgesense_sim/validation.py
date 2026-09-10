from __future__ import annotations

from dataclasses import dataclass

from forgesense_ml.reference import STARTUP_SETTLE_SAMPLES, fit_reference_model
from forgesense_ml.runtime import EdgeInferenceRuntime
from forgesense_protocol import encode_ml_observation

from .closed_loop import SafetyControllerModel, SafetyState
from .scenarios import build_scenario, run_scenario


@dataclass(frozen=True)
class ValidationResult:
    scenario: str
    fault_start: int | None
    first_warning: int | None
    terminal_index: int | None
    terminal_state: SafetyState | None
    hard_critical_at_terminal: bool | None
    accepted_ml_frames: int
    passed: bool
    rationale: str


def _run_machine_scenario(name: str) -> ValidationResult:
    model = fit_reference_model()
    runtime = EdgeInferenceRuntime(model, window_size=8)
    scenario = build_scenario(name)
    samples = run_scenario(scenario)
    controller = SafetyControllerModel(watchdog_timeout_steps=15)

    sequence = 0
    accepted = 0
    first_warning: int | None = None
    terminal_index: int | None = None
    terminal_state: SafetyState | None = None
    hard_critical_at_terminal: bool | None = None

    for index, sample in enumerate(samples):
        observation = runtime.ingest(sample)
        operational_ready = (
            index >= STARTUP_SETTLE_SAMPLES and observation is not None
        )
        frame = None
        if operational_ready:
            frame = encode_ml_observation(
                observation,
                sequence=sequence,
                timestamp_ms=int(sample.time_s * 1000) & 0xFFFFFFFF,
            )
            sequence = (sequence + 1) & 0xFFFF

        output = controller.step(
            sample,
            startup_done=operational_ready,
            ml_frame=frame,
        )
        accepted += int(output.accepted_ml)
        if first_warning is None and output.state is SafetyState.WARNING:
            first_warning = index
        if (
            index >= STARTUP_SETTLE_SAMPLES
            and output.state in (SafetyState.SHUTDOWN, SafetyState.FAULT_LATCHED)
        ):
            terminal_index = index
            terminal_state = output.state
            hard_critical_at_terminal = output.hard_critical
            break

    if name == "normal":
        passed = terminal_index is None
        rationale = "normal envelope remained operational" if passed else "false terminal action during normal envelope"
    elif name == "sensor_dropout":
        passed = (
            terminal_index == scenario.fault_start
            and terminal_state is SafetyState.FAULT_LATCHED
            and hard_critical_at_terminal is True
        )
        rationale = "invalid sensor path latched deterministic hard fault" if passed else "sensor invalidity did not fail closed immediately"
    else:
        passed = (
            scenario.fault_start is not None
            and terminal_index is not None
            and terminal_index >= scenario.fault_start
            and terminal_state is SafetyState.SHUTDOWN
            and hard_critical_at_terminal is False
        )
        rationale = "ML requested bounded early shutdown before hard critical limit" if passed else "fault scenario did not meet bounded early-shutdown expectation"

    return ValidationResult(
        scenario=name,
        fault_start=scenario.fault_start,
        first_warning=first_warning,
        terminal_index=terminal_index,
        terminal_state=terminal_state,
        hard_critical_at_terminal=hard_critical_at_terminal,
        accepted_ml_frames=accepted,
        passed=passed,
        rationale=rationale,
    )


def _run_link_loss() -> ValidationResult:
    model = fit_reference_model()
    runtime = EdgeInferenceRuntime(model, window_size=8)
    samples = run_scenario(build_scenario("normal"))
    controller = SafetyControllerModel(watchdog_timeout_steps=15)
    sequence = 0
    link_loss_start = 180
    terminal_index = None

    for index, sample in enumerate(samples):
        observation = runtime.ingest(sample)
        ready = index >= STARTUP_SETTLE_SAMPLES and observation is not None
        frame = None
        if ready and index < link_loss_start:
            frame = encode_ml_observation(
                observation,
                sequence=sequence,
                timestamp_ms=int(sample.time_s * 1000) & 0xFFFFFFFF,
            )
            sequence = (sequence + 1) & 0xFFFF
        output = controller.step(sample, startup_done=ready, ml_frame=frame)
        if index >= link_loss_start and output.state is SafetyState.SHUTDOWN:
            terminal_index = index
            break

    expected = link_loss_start + controller.watchdog_timeout_steps - 1
    passed = terminal_index == expected
    return ValidationResult(
        scenario="link_loss",
        fault_start=link_loss_start,
        first_warning=None,
        terminal_index=terminal_index,
        terminal_state=SafetyState.SHUTDOWN if terminal_index is not None else None,
        hard_critical_at_terminal=False if terminal_index is not None else None,
        accepted_ml_frames=max(0, link_loss_start - STARTUP_SETTLE_SAMPLES),
        passed=passed,
        rationale="watchdog removed load authority after intelligence link loss" if passed else f"watchdog timing mismatch; expected terminal sample {expected}",
    )


def _run_emergency() -> ValidationResult:
    model = fit_reference_model()
    runtime = EdgeInferenceRuntime(model, window_size=8)
    samples = run_scenario(build_scenario("normal"))
    controller = SafetyControllerModel(watchdog_timeout_steps=15)
    sequence = 0
    emergency_index = 180
    terminal_index = None

    for index, sample in enumerate(samples):
        observation = runtime.ingest(sample)
        ready = index >= STARTUP_SETTLE_SAMPLES and observation is not None
        frame = None
        if ready:
            frame = encode_ml_observation(
                observation,
                sequence=sequence,
                timestamp_ms=int(sample.time_s * 1000) & 0xFFFFFFFF,
            )
            sequence = (sequence + 1) & 0xFFFF
        output = controller.step(
            sample,
            startup_done=ready,
            ml_frame=frame,
            emergency=index == emergency_index,
        )
        if output.state is SafetyState.FAULT_LATCHED:
            terminal_index = index
            break

    passed = terminal_index == emergency_index
    return ValidationResult(
        scenario="emergency",
        fault_start=emergency_index,
        first_warning=None,
        terminal_index=terminal_index,
        terminal_state=SafetyState.FAULT_LATCHED if terminal_index is not None else None,
        hard_critical_at_terminal=False if terminal_index is not None else None,
        accepted_ml_frames=max(0, emergency_index - STARTUP_SETTLE_SAMPLES + 1),
        passed=passed,
        rationale="emergency path latched fault on the same control step" if passed else "emergency path was not deterministic",
    )


def run_validation_matrix() -> list[ValidationResult]:
    results = [
        _run_machine_scenario("normal"),
        _run_machine_scenario("bearing_degradation"),
        _run_machine_scenario("overcurrent"),
        _run_machine_scenario("cooling_loss"),
        _run_machine_scenario("sensor_dropout"),
        _run_link_loss(),
        _run_emergency(),
    ]
    return results
