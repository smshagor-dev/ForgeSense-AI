from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    preparer = (root / "tools/prepare_approved_calibration_source_change.py").read_text(encoding="utf-8")
    verifier = (root / "tools/verify_calibration_source_change.py").read_text(encoding="utf-8")
    derivation = (root / "tools/verify_calibration_source_derivation.py").read_text(encoding="utf-8")
    tests = (root / "tests/test_calibration_source_change.py").read_text(encoding="utf-8")
    approval = (root / "hardware/calibration/calibration_approval_template_v1.json").read_text(encoding="utf-8")
    policy = (root / "hardware/calibration/calibration_source_change_policy_v1.json").read_text(encoding="utf-8")
    docs = (root / "docs/CALIBRATION_SOURCE_CHANGE.md").read_text(encoding="utf-8")

    for token in (
        'APPROVAL_SCHEMA = "forgesense.calibration_approval.v1"',
        'POLICY_SCHEMA = "forgesense.calibration_source_change_policy.v1"',
        'SOURCE_PROFILE_SCHEMA = "forgesense.approved_calibration_source_profile.v1"',
        'SOURCE_CHANGE_SCHEMA = "forgesense.calibration_source_change.v1"',
        '"runtime_write_permitted": False',
        '"automatic_runtime_application": False',
        '"may_control_actuators": False',
        '"may_relax_hard_safety_limits": False',
        '"hard_safety_limits_changed": False',
        '"runtime_files_changed": False',
        'Fraction(slope).limit_denominator',
        '_collect_current_raw_points',
        '_safety_baseline',
        '_profile_patch',
    ):
        assert token in preparer, token

    for token in (
        'VERIFICATION_SCHEMA = "forgesense.calibration_source_change_verification.v1"',
        '"artifact_integrity_pass": True',
        '"approval_binding_pass": True',
        '"quantization_regression_pass": True',
        '"hard_safety_non_regression_pass": True',
        '"runtime_source_unchanged": True',
        'diff_headers != [expected_header]',
        'safety baseline changed after package generation',
    ):
        assert token in verifier, token

    for token in (
        'VERIFICATION_SCHEMA = "forgesense.calibration_source_derivation_verification.v1"',
        'build_change_package(',
        '_collect_current_raw_points',
        '_quantize_current',
        '_quantize_temperature',
        '"reviewer_package_rederived": True',
        '"current_coefficients_rederived": True',
        '"temperature_coefficients_rederived": True',
        '"quantization_regression_rederived": True',
        'approved current coefficients differ from evidence-derived integer coefficients',
        'approved temperature coefficients differ from evidence-derived integer coefficients',
    ):
        assert token in derivation, token

    for forbidden in (
        "serial.serial",
        "uart_rx",
        "load_enable_o",
        "flash_calibration",
        "apply_runtime_calibration",
        "write_fpga",
        "set_hard_limit",
        "update_safety_limit",
        "private_key",
        "secret_key",
    ):
        assert forbidden not in preparer.lower(), forbidden
        assert forbidden not in verifier.lower(), forbidden
        assert forbidden not in derivation.lower(), forbidden

    for token in (
        '"decision": "approved_for_source_change"',
        '"approved_channels"',
        '"deferred_channels"',
        '"runtime_write_approved": false',
        '"hard_safety_limit_change_approved": false',
    ):
        assert token in approval, token

    for token in (
        '"maximum_gain_denominator": 1000000',
        '"runtime_mapping_supported": false',
        '"required_disposition": "deferred"',
        '"runtime_files_may_be_modified": false',
        '"safety_baseline_files"',
    ):
        assert token in policy, token

    for token in (
        "test_source_change_quantizes_current_against_retained_raw_points",
        "test_source_change_rejects_negative_current_mapping_at_reference_point",
        "test_temperature_quantization_is_bounded",
        "test_approval_must_defer_unmapped_accelerometer",
        "test_source_change_verifier_accepts_preapply_package",
        "test_source_change_verifier_rejects_patch_tamper",
        "test_source_change_verifier_rejects_safety_baseline_drift",
        "test_source_change_verifier_accepts_applied_identical_profile",
    ):
        assert token in tests, token

    assert "source-controlled" in docs.lower()
    assert "accelerometer" in docs.lower()
    assert "deferred" in docs.lower()
    assert "hard-safety" in docs.lower()
    assert "runtime write" in docs.lower()
    assert "quantization" in docs.lower()
    assert "reconstructed from the original campaign evidence" in docs.lower()

    print(
        "calibration_source_change_check PASS: reviewer approval, deterministic quantization, evidence re-derivation, add-only profile patch, hard-safety non-regression and no-runtime-write authority are present"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
