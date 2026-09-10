from forgesense_ml.reference import STARTUP_SETTLE_SAMPLES, fit_reference_model
from forgesense_ml.runtime import EdgeInferenceRuntime
from forgesense_protocol import HealthClass, MlObservation, VALID_OBSERVATION, encode_ml_observation
from forgesense_sim import SafetyControllerModel, SafetyState, build_scenario, run_scenario


def test_watchdog_is_held_during_ml_warmup_then_supervises_link() -> None:
    snapshots = run_scenario(build_scenario("normal"))
    controller = SafetyControllerModel(watchdog_timeout_steps=5)
    for snapshot in snapshots[:20]:
        output = controller.step(snapshot, startup_done=False)
        assert output.state is SafetyState.STARTUP

    normal = MlObservation(1, 1, 1, VALID_OBSERVATION, 0.1, HealthClass.NORMAL, 0.95, 0)
    frame = encode_ml_observation(normal, sequence=1, timestamp_ms=2000)
    output = controller.step(snapshots[20], startup_done=True, ml_frame=frame)
    assert output.state is SafetyState.RUN

    for snapshot in snapshots[21:25]:
        output = controller.step(snapshot, startup_done=True)
        assert output.state is SafetyState.RUN
    output = controller.step(snapshots[25], startup_done=True)
    assert output.state is SafetyState.SHUTDOWN
    assert not output.load_enable


def test_replayed_frames_do_not_keep_watchdog_alive() -> None:
    snapshots = run_scenario(build_scenario("normal"))
    controller = SafetyControllerModel(watchdog_timeout_steps=3)
    normal = MlObservation(1, 1, 1, VALID_OBSERVATION, 0.1, HealthClass.NORMAL, 0.9, 0)
    frame = encode_ml_observation(normal, sequence=7, timestamp_ms=100)
    assert controller.step(snapshots[100], startup_done=True, ml_frame=frame).state is SafetyState.RUN
    assert controller.step(snapshots[101], startup_done=True, ml_frame=frame).state is SafetyState.RUN
    assert controller.step(snapshots[102], startup_done=True, ml_frame=frame).state is SafetyState.RUN
    output = controller.step(snapshots[103], startup_done=True, ml_frame=frame)
    assert output.state is SafetyState.SHUTDOWN
    assert output.rejection_reason == "replay-or-duplicate"


def test_bearing_degradation_triggers_bounded_ml_shutdown_before_hard_limit() -> None:
    model = fit_reference_model()
    runtime = EdgeInferenceRuntime(model, window_size=8)
    samples = run_scenario(build_scenario("bearing_degradation"))
    controller = SafetyControllerModel(watchdog_timeout_steps=15)
    shutdown_index = None
    hard_critical_at_shutdown = None
    sequence = 0

    for index, sample in enumerate(samples):
        frame = None
        observation = runtime.ingest(sample)
        ready = index >= STARTUP_SETTLE_SAMPLES and observation is not None
        if ready:
            frame = encode_ml_observation(
                observation,
                sequence=sequence,
                timestamp_ms=int(sample.time_s * 1000),
            )
            sequence = (sequence + 1) & 0xFFFF
        output = controller.step(
            sample,
            startup_done=ready,
            ml_frame=frame,
        )
        if (
            output.state in (SafetyState.SHUTDOWN, SafetyState.FAULT_LATCHED)
            and index >= STARTUP_SETTLE_SAMPLES
        ):
            shutdown_index = index
            hard_critical_at_shutdown = output.hard_critical
            break

    assert shutdown_index is not None
    assert shutdown_index >= 220
    assert hard_critical_at_shutdown is False


def test_last_accepted_warning_persists_until_fresh_normal_observation() -> None:
    snapshots = run_scenario(build_scenario("normal"))
    controller = SafetyControllerModel(watchdog_timeout_steps=6)
    warning = MlObservation(1, 1, 1, VALID_OBSERVATION, 0.8, HealthClass.WARNING, 0.9, 0)
    warning_frame = encode_ml_observation(warning, sequence=10, timestamp_ms=1000)

    output = controller.step(snapshots[100], startup_done=True, ml_frame=warning_frame)
    assert output.state is SafetyState.WARNING
    assert output.warning_active

    for snapshot in snapshots[101:104]:
        output = controller.step(snapshot, startup_done=True)
        assert output.state is SafetyState.WARNING
        assert output.warning_active

    normal = MlObservation(1, 1, 1, VALID_OBSERVATION, 0.1, HealthClass.NORMAL, 0.95, 0)
    normal_frame = encode_ml_observation(normal, sequence=11, timestamp_ms=1400)
    output = controller.step(snapshots[104], startup_done=True, ml_frame=normal_frame)
    assert output.state is SafetyState.RUN
    assert not output.warning_active


def test_first_operational_critical_observation_never_energizes_load() -> None:
    snapshots = run_scenario(build_scenario("normal"))
    controller = SafetyControllerModel(watchdog_timeout_steps=6)
    critical = MlObservation(1, 1, 1, VALID_OBSERVATION, 0.95, HealthClass.CRITICAL, 0.95, 0)
    frame = encode_ml_observation(critical, sequence=1, timestamp_ms=1000)

    output = controller.step(snapshots[100], startup_done=True, ml_frame=frame)
    assert output.state is SafetyState.SHUTDOWN
    assert not output.load_enable
