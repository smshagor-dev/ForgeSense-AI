from forgesense_sim.scenarios import build_scenario, run_scenario


def test_simulation_is_deterministic() -> None:
    a = run_scenario(build_scenario("bearing_degradation"))
    b = run_scenario(build_scenario("bearing_degradation"))
    assert a == b


def test_bearing_degradation_changes_condition_features() -> None:
    normal = run_scenario(build_scenario("normal"))
    bearing = run_scenario(build_scenario("bearing_degradation"))
    assert bearing[-1].vibration_rms_g > normal[-1].vibration_rms_g * 2.0
    assert bearing[-1].current_a > normal[-1].current_a


def test_sensor_dropout_is_explicit_not_silently_numeric() -> None:
    rows = run_scenario(build_scenario("sensor_dropout"))
    invalid = [row for row in rows if not row.all_valid]
    assert invalid
    assert any(not row.valid_vibration for row in invalid)
