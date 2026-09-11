from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    verifier = (root / "tools/verify_calibration_bundle.py").read_text(encoding="utf-8")
    preparer = (root / "tools/prepare_calibration_change_package.py").read_text(encoding="utf-8")
    tests = (root / "tests/test_calibration_bundle_verification.py").read_text(encoding="utf-8")
    docs = (root / "docs/CALIBRATION_BUNDLE_VERIFICATION.md").read_text(encoding="utf-8")

    for token in (
        'VERIFICATION_SCHEMA = "forgesense.calibration_bundle_verification.v1"',
        'EVIDENCE_INDEX_SCHEMA = "forgesense.calibration_evidence_index.v1"',
        '"bundle_integrity_pass": True',
        '"semantic_chain_pass": True',
        '"source_provenance_pass"',
        '"verification_only": True',
        '"automatic_runtime_application": False',
        '"may_control_actuators": False',
        '"may_relax_hard_safety_limits": False',
        '_canonical_sha256(capture)',
        'diagnostic evidence hash mismatch',
    ):
        assert token in verifier, token

    for token in (
        'CHANGE_PACKAGE_SCHEMA = "forgesense.calibration_change_package.v1"',
        'SIGNING_REQUEST_SCHEMA = "forgesense.calibration_signing_request.v1"',
        'SIGNING_DOMAIN = "ForgeSense-Calibration-Change-Package-v1"',
        '"runtime_write_permitted": False',
        '"external_signature_required": True',
        '"digital_signature_present": False',
        'source_provenance_pass',
        'review_ready',
        'tempfile.mkdtemp',
        'staging.rename(out_dir)',
    ):
        assert token in preparer, token

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
        assert forbidden not in verifier.lower(), forbidden
        assert forbidden not in preparer.lower(), forbidden

    for token in (
        "test_bundle_integrity_can_be_verified_without_source_files",
        "test_full_source_provenance_verifies_session_policy_and_diagnostic_files",
        "test_generated_artifact_tamper_is_rejected",
        "test_evidence_root_tamper_is_rejected",
        "test_original_diagnostic_tamper_is_rejected_by_source_provenance",
        "test_change_package_requires_review_ready_campaign",
        "test_reviewer_ready_package_has_no_runtime_write_and_external_signing_request",
        "test_change_package_publication_is_atomic_and_never_overwrites",
    ):
        assert token in tests, token

    assert "not a digital signature" in docs.lower()
    assert "source provenance" in docs.lower()
    assert "runtime write" in docs.lower()
    assert "external signing" in docs.lower()
    assert "tamper" in docs.lower()

    print(
        "calibration_bundle_verification_check PASS: tamper detection, source provenance, reviewer gate and external-signing boundary are present"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
