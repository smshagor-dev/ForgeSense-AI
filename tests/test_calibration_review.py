from __future__ import annotations

from copy import deepcopy

import pytest

from tools.capture_calibration import build_proposal
from tools.review_calibration import review_proposals


def policy() -> dict:
    return {
        "schema": "forgesense.calibration_review_policy.v1",
        "policy_id": "CAL-TEST-001",
        "minimum_runs": 3,
        "require_same_board_revisions": True,
        "require_same_repository_commit": True,
        "current": {
            "maximum_slope_span_ppm": 10000.0,
            "maximum_intercept_span_ma": 25.0,
            "maximum_run_rmse_ma": 50.0,
        },
        "temperature": {
            "maximum_offset_span_c": 0.30,
            "maximum_run_residual_rmse_c": 0.20,
        },
        "accelerometer": {
            "maximum_axis_bias_span_mg": 50.0,
            "maximum_run_axis_stddev_mg": 25.0,
            "maximum_abs_bias_mg": 250.0,
        },
        "uncertainty": {
            "require_declared": True,
            "maximum_reference_current_ma_k2": 25.0,
            "maximum_reference_temperature_c_k2": 0.20,
            "maximum_reference_accelerometer_mg_k2": 25.0,
        },
    }


def capture(run: int, slope_scale: float = 1.0, temp_offset_c: float = 0.20, accel_x_bias_mg: float = 12.0) -> dict:
    raw_values = [0, 1_000_000, 2_000_000, 4_000_000, 6_000_000]
    current_points = [
        {
            "adc_raw": raw,
            "reference_current_a": (100.0 + raw * 0.0005 * slope_scale) / 1000.0,
        }
        for raw in raw_values
    ]
    return {
        "schema": "forgesense.calibration_capture.v1",
        "capture_id": f"CAL-RUN-{run:03d}",
        "repository_commit": "a" * 40,
        "boards": {
            "fpga_revision": "fpga-a",
            "esp32_revision": "esp32-a",
            "sensor_board_revision": "sensor-a",
        },
        "instruments": [
            {
                "type": "synthetic_reference",
                "manufacturer_model": "test",
                "asset_or_serial": "test",
                "calibration_status": "synthetic",
            }
        ],
        "environment": {"ambient_temperature_c": 25.0},
        "measurement_uncertainty": {
            "reference_current_ma_k2": 10.0,
            "reference_temperature_c_k2": 0.10,
            "reference_accelerometer_mg_k2": 10.0,
        },
        "evidence": [{"file": f"run-{run}.json", "sha256": "b" * 64, "description": "synthetic fixture"}],
        "current": {
            "minimum_raw_span": 100000.0,
            "minimum_r2": 0.999,
            "maximum_rmse_ma": 10.0,
            "points": current_points,
        },
        "temperature": {
            "maximum_offset_rmse_c": 0.05,
            "points": [
                {"tmp117_temperature_c": reference - temp_offset_c, "reference_temperature_c": reference}
                for reference in (20.0, 25.0, 30.0)
            ],
        },
        "accelerometer": {
            "expected_stationary_mg": {"x": 0.0, "y": 0.0, "z": 1000.0},
            "maximum_abs_bias_mg": 100.0,
            "stationary_samples_mg": [
                {
                    "x": accel_x_bias_mg + ((i % 3) - 1) * 2.0,
                    "y": -8.0 + ((i % 5) - 2) * 1.0,
                    "z": 1025.0 + ((i % 4) - 1.5) * 2.0,
                }
                for i in range(20)
            ],
        },
    }


def proposal(run: int, **kwargs: float) -> dict:
    result = build_proposal(capture(run, **kwargs))
    result["source_capture_sha256"] = f"{run + 1:x}" * 64
    return result


def test_three_consistent_runs_are_review_ready_without_runtime_authority() -> None:
    result = review_proposals(
        [
            proposal(0, slope_scale=0.998, temp_offset_c=0.19, accel_x_bias_mg=10.0),
            proposal(1, slope_scale=1.000, temp_offset_c=0.20, accel_x_bias_mg=12.0),
            proposal(2, slope_scale=1.002, temp_offset_c=0.21, accel_x_bias_mg=14.0),
        ],
        policy(),
    )
    assert result["review_ready"] is True
    assert result["authority"]["reviewer_approval_required"] is True
    assert result["authority"]["source_control_change_required"] is True
    assert result["authority"]["automatic_runtime_application"] is False
    assert result["authority"]["may_relax_hard_safety_limits"] is False
    assert result["current"]["repeatability_pass"] is True
    assert result["temperature"]["repeatability_pass"] is True
    assert result["accelerometer"]["repeatability_pass"] is True
    assert result["provenance"]["measurement_uncertainty_complete"] is True


def test_board_revision_mismatch_blocks_review_readiness() -> None:
    proposals = [proposal(0), proposal(1), proposal(2)]
    proposals[2]["provenance"]["boards"]["sensor_board_revision"] = "sensor-b"
    result = review_proposals(proposals, policy())
    assert result["review_ready"] is False
    assert result["provenance"]["board_revisions_consistent"] is False
    assert result["checks"]["board_gate_pass"] is False


def test_large_current_gain_drift_is_rejected() -> None:
    result = review_proposals(
        [
            proposal(0, slope_scale=0.98),
            proposal(1, slope_scale=1.00),
            proposal(2, slope_scale=1.02),
        ],
        policy(),
    )
    assert result["review_ready"] is False
    assert result["current"]["repeatability_pass"] is False
    assert result["current"]["slope_span_ppm"] > policy()["current"]["maximum_slope_span_ppm"]


def test_missing_uncertainty_blocks_review_readiness() -> None:
    proposals = [proposal(0), proposal(1), proposal(2)]
    proposals[1]["provenance"]["measurement_uncertainty"] = {}
    result = review_proposals(proposals, policy())
    assert result["review_ready"] is False
    assert result["provenance"]["measurement_uncertainty_complete"] is False
    assert result["checks"]["uncertainty_limits_pass"] is False


def test_authority_tamper_is_rejected() -> None:
    proposals = [proposal(0), proposal(1), proposal(2)]
    proposals[0]["authority"]["automatic_runtime_application"] = True
    with pytest.raises(ValueError, match="forbid automatic runtime application"):
        review_proposals(proposals, policy())


def test_too_few_runs_is_not_review_ready() -> None:
    result = review_proposals([proposal(0), proposal(1)], policy())
    assert result["review_ready"] is False
    assert result["provenance"]["run_count_pass"] is False
