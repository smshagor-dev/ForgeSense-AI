from __future__ import annotations

from forgesense_ml.reference import STARTUP_SETTLE_SAMPLES, fit_reference_model
from forgesense_ml.runtime import EdgeInferenceRuntime
from forgesense_protocol import encode_ml_observation
from forgesense_sim import SafetyControllerModel, SafetyState, build_scenario, run_scenario


def main() -> int:
    model = fit_reference_model()
    runtime = EdgeInferenceRuntime(model, window_size=8)
    scenario = build_scenario("bearing_degradation")
    samples = run_scenario(scenario)
    controller = SafetyControllerModel(watchdog_timeout_steps=15)
    sequence = 0
    accepted = 0
    rejected = 0
    shutdown_index = None
    shutdown_state = None
    hard_critical = None

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
                timestamp_ms=int(sample.time_s * 1000),
            )
            sequence = (sequence + 1) & 0xFFFF
        output = controller.step(
            sample,
            startup_done=operational_ready,
            ml_frame=frame,
        )
        accepted += int(output.accepted_ml)
        rejected += int(
            output.rejection_reason is not None and not output.accepted_ml
        )
        if (
            index >= STARTUP_SETTLE_SAMPLES
            and output.state in (SafetyState.SHUTDOWN, SafetyState.FAULT_LATCHED)
        ):
            shutdown_index = index
            shutdown_state = output.state.name
            hard_critical = output.hard_critical
            break

    print(f"scenario={scenario.name}")
    print(f"fault_start={scenario.fault_start}")
    print(f"shutdown_index={shutdown_index}")
    print(f"shutdown_state={shutdown_state}")
    print(f"hard_critical_at_shutdown={hard_critical}")
    print(f"accepted_ml_frames={accepted}")
    print(f"rejected_ml_frames={rejected}")

    if shutdown_index is None or scenario.fault_start is None:
        return 1
    if shutdown_index < scenario.fault_start or hard_critical:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
