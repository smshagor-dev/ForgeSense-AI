from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    tool = (root / "tools/assemble_calibration_capture.py").read_text(encoding="utf-8")
    template = (root / "hardware/calibration/calibration_session_template_v1.json").read_text(encoding="utf-8")
    tests = (root / "tests/test_calibration_capture_assembler.py").read_text(encoding="utf-8")
    docs = (root / "docs/CALIBRATION_SESSION_ASSEMBLY.md").read_text(encoding="utf-8")

    for token in (
        'SESSION_SCHEMA = "forgesense.calibration_session.v1"',
        'CAPTURE_SCHEMA = "forgesense.calibration_capture.v1"',
        'DIAGNOSTIC_SCHEMA = "forgesense.calibration_diagnostic_capture.v1"',
        '"assembled_from_read_only_diagnostics": True',
        '"independent_reference_values_required": True',
        '"automatic_runtime_application": False',
        '"may_relax_hard_safety_limits": False',
        '"reference_current_a"',
        '"reference_temperature_c"',
        '"sha256"',
        '"usable_samples"',
        'build_proposal(capture)',
    ):
        assert token in tool, token

    for forbidden in (
        "serial.serial",
        "uart_rx",
        "load_enable",
        "flash_calibration",
        "apply_runtime_calibration",
        "write_fpga",
        "set_hard_limit",
        "update_safety_limit",
    ):
        assert forbidden not in tool.lower(), forbidden

    for token in (
        '"schema": "forgesense.calibration_session.v1"',
        '"repository_commit"',
        '"measurement_uncertainty"',
        '"reference_current_a"',
        '"reference_temperature_c"',
        '"diagnostic_files"',
        '"expected_stationary_mg"',
    ):
        assert token in template, token

    for token in (
        "test_assembler_builds_proposal_compatible_capture_from_trusted_diagnostics",
        "test_evidence_hash_matches_raw_diagnostic_file",
        "test_failed_or_sequence_broken_diagnostic_is_rejected",
        "test_tampered_diagnostic_authority_is_rejected",
        "test_duplicate_source_within_current_characterization_is_rejected",
        "test_duplicate_accelerometer_source_is_rejected",
        "test_inconsistent_reported_usable_sample_count_is_rejected",
        "test_missing_independent_reference_value_is_rejected",
    ):
        assert token in tests, token

    assert "independent reference" in docs.lower()
    assert "does not apply calibration" in docs.lower()
    assert "sha-256" in docs.lower()
    assert "at least five" in docs.lower()
    assert "at least three" in docs.lower()
    assert "20" in docs

    print("calibration_assembler_check PASS: independent-reference assembly, evidence hashing, duplicate rejection, summary consistency and review-only authority are present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
