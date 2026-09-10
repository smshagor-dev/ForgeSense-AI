from forgesense_sim.validation import run_validation_matrix


def test_full_validation_matrix_passes() -> None:
    results = run_validation_matrix()
    assert len(results) == 7
    assert all(result.passed for result in results)


def test_normal_envelope_has_no_false_terminal_action() -> None:
    result = next(
        item for item in run_validation_matrix() if item.scenario == "normal"
    )
    assert result.terminal_index is None
    assert result.first_warning is None


def test_fault_authority_split_is_preserved() -> None:
    results = {item.scenario: item for item in run_validation_matrix()}
    for name in ("bearing_degradation", "overcurrent", "cooling_loss"):
        result = results[name]
        assert result.terminal_state.name == "SHUTDOWN"
        assert result.hard_critical_at_terminal is False

    dropout = results["sensor_dropout"]
    assert dropout.terminal_state.name == "FAULT_LATCHED"
    assert dropout.hard_critical_at_terminal is True

    emergency = results["emergency"]
    assert emergency.terminal_state.name == "FAULT_LATCHED"
    assert emergency.terminal_index == emergency.fault_start
