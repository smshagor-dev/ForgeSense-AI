from __future__ import annotations

from copy import deepcopy

import pytest

from tools.capture_calibration import build_proposal


def capture() -> dict:
    return {
        "schema": "forgesense.calibration_capture.v1",
        "capture_id": "CAL-TEST-001",
        "repository_commit": "a" * 40,
        "boards": {
            "fpga_revision": "test",
            "esp32_revision": "test",
            "sensor_board_revision": "test",
        },
        "instruments": [{"type": "synthetic", "manufacturer_model": "test", "asset_or_serial": "test", "calibration_status": "synthetic"}],
        "environment": {"ambient_temperature_c": 25.0},
        "evidence": [{"file": "synthetic.json", "sha256": "b" * 64, "description": "unit-test fixture"}],
        "current": {
            "minimum_raw_span": 100000.0,
            "minimum_r2": 0.999,
            "maximum_rmse_ma": 10.0,
            "points": [
                {"adc_raw": 0, "reference_current_a": 0.1},
                {"adc_raw": 1_000_000, "reference_current_a": 0.6},
                {"adc_raw": 2_000_000, "reference_current_a": 1.1},
                {"adc_raw": 4_000_000, "reference_current_a": 2.1},
                {"adc_raw": 6_000_000, "reference_current_a": 3.1},
            ],
        },
        "temperature": {
            "maximum_offset_rmse_c": 0.05,
            "points": [
                {"tmp117_temperature_c": 19.8, "reference_temperature_c": 20.0},
                {"tmp117_temperature_c": 24.8, "reference_temperature_c": 25.0},
                {"tmp117_temperature_c": 29.8, "reference_temperature_c": 30.0},
            ],
        },
        "accelerometer": {
            "expected_stationary_mg": {"x": 0.0, "y": 0.0, "z": 1000.0},
            "maximum_abs_bias_mg": 100.0,
            "stationary_samples_mg": [{"x": 12.0, "y": -8.0, "z": 1025.0} for _ in range(20)],
        },
    }


def test_good_capture_produces_review_only_proposal() -> None:
    proposal = build_proposal(capture())
    assert proposal["proposal_quality_pass"] is True
    assert proposal["authority"]["review_required"] is True
    assert proposal["authority"]["automatic_runtime_application"] is False
    assert proposal["authority"]["may_relax_hard_safety_limits"] is False
    assert proposal["current"]["r2"] == pytest.approx(1.0)
    assert proposal["current"]["integer_candidate"]["gain_numerator"] > 0
    assert proposal["temperature"]["offset_c"] == pytest.approx(0.2)
    assert proposal["accelerometer"]["bias_mg"] == {"x": 12.0, "y": -8.0, "z": 25.0}
    assert proposal["accelerometer"]["correction_mg_candidate"] == {"x": -12, "y": 8, "z": -25}


def test_poor_current_fit_marks_proposal_quality_fail() -> None:
    data = capture()
    data["current"]["points"][2]["reference_current_a"] = 2.5
    proposal = build_proposal(data)
    assert proposal["current"]["proposal_quality_pass"] is False
    assert proposal["proposal_quality_pass"] is False


def test_missing_provenance_hash_is_rejected() -> None:
    data = capture()
    data["evidence"][0]["sha256"] = "bad"
    with pytest.raises(ValueError, match="SHA-256"):
        build_proposal(data)


def test_too_few_accelerometer_samples_is_rejected() -> None:
    data = capture()
    data["accelerometer"]["stationary_samples_mg"] = data["accelerometer"]["stationary_samples_mg"][:5]
    with pytest.raises(ValueError, match="at least 20"):
        build_proposal(data)
