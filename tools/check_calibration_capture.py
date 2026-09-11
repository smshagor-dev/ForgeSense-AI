from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    tool = (root / "tools/capture_calibration.py").read_text(encoding="utf-8")
    template = (root / "hardware/calibration/calibration_capture_template_v1.json").read_text(encoding="utf-8")
    tests = (root / "tests/test_calibration_capture.py").read_text(encoding="utf-8")
    docs = (root / "docs/CALIBRATION_CAPTURE.md").read_text(encoding="utf-8")

    for token in (
        '"automatic_runtime_application": False',
        '"may_relax_hard_safety_limits": False',
        '"review_required": True',
        '"schema": "forgesense.calibration_proposal.v1"',
        '"fit_target": "adc_raw_to_current_milli_a"',
        '"constant_offset_characterization"',
        '"stationary_axis_bias_characterization"',
        '"measurement_uncertainty"',
        '"axis_stddev_mg"',
    ):
        assert token in tool, token

    forbidden = (
        "write_fpga",
        "flash_calibration",
        "apply_runtime_calibration",
        "update_safety_limit",
    )
    lowered = tool.lower()
    for token in forbidden:
        assert token not in lowered

    assert '"schema": "forgesense.calibration_capture.v1"' in template
    assert '"repository_commit"' in template
    assert '"fpga_revision"' in template
    assert '"esp32_revision"' in template
    assert '"sensor_board_revision"' in template
    assert '"sha256"' in template
    assert '"measurement_uncertainty"' in template
    assert '"reference_current_ma_k2"' in template
    assert '"reference_temperature_c_k2"' in template
    assert '"reference_accelerometer_mg_k2"' in template

    for token in (
        "test_good_capture_produces_review_only_proposal",
        "test_poor_current_fit_marks_proposal_quality_fail",
        "test_missing_provenance_hash_is_rejected",
        "test_too_few_accelerometer_samples_is_rejected",
    ):
        assert token in tests

    assert "does not modify FPGA or ESP32 runtime calibration" in docs
    assert "not a safety-limit approval" in docs
    assert "measurement uncertainty" in docs.lower()
    assert "repeated-run review" in docs.lower()
    assert "review" in docs.lower()

    print("calibration_capture_check PASS: proposal-only calibration evidence path, uncertainty metadata and tests are present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
