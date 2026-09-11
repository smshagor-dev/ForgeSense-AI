from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    protocol = (root / "firmware/esp32_calibration_maintenance/main/maintenance_protocol.hpp").read_text(encoding="utf-8")
    maintenance_app = (root / "firmware/esp32_calibration_maintenance/main/app_main.cpp").read_text(encoding="utf-8")
    recovery_host = (root / "commissioning/forgesense_commission/recovery.py").read_text(encoding="utf-8")
    preparer = (root / "tools/prepare_calibration_recovery.py").read_text(encoding="utf-8")
    verifier = (root / "tools/verify_calibration_recovery.py").read_text(encoding="utf-8")
    physical_tool = (root / "tools/run_physical_calibration_provisioning.py").read_text(encoding="utf-8")
    signing_request = (root / "tools/prepare_calibration_maintenance_authorization.py").read_text(encoding="utf-8")
    policy_validator = (root / "tools/validate_signed_provisioning_policy.py").read_text(encoding="utf-8")
    tests = (root / "tests/test_calibration_recovery.py").read_text(encoding="utf-8")
    production_app = (root / "firmware/esp32/main/app_main.cpp").read_text(encoding="utf-8")
    transparent_bridge = (root / "firmware/esp32_commissioning/main/app_main.cpp").read_text(encoding="utf-8")
    provisioning_policy = json.loads(
        (root / "hardware/calibration/calibration_provisioning_policy_v1.json").read_text(encoding="utf-8")
    )
    authority_policy = json.loads(
        (root / "hardware/calibration/maintenance_authority_policy_v1.json").read_text(encoding="utf-8")
    )

    for token in (
        "QueryActiveRecord = 0x05",
        "ActiveRecordResponse = 0x85",
    ):
        assert token in protocol, token
    for forbidden in (
        "RotateAuthorityKey",
        "UpdateAuthorityKey",
        "SetAuthorityKey",
        "WriteAuthorityKey",
    ):
        assert forbidden not in protocol, forbidden

    for token in (
        "handle_query_active_record",
        "g_store.load_active(active)",
        "encode_calibration_record(active, encoded)",
        "MaintenanceOpcode::ActiveRecordResponse",
    ):
        assert token in maintenance_app, token

    for token in (
        'RECOVERY_INTENT_SCHEMA = "forgesense.calibration_recovery_intent.v1"',
        "query_active_record",
        "validate_recovery_runtime_binding",
        "candidate != installed + 1",
        "active record SHA-256 changed",
        "increment_exactly_one",
        "verify_recovery_aware_reboot",
        "exact_record_sha256_match",
        '"sequence_decrement_performed": False',
    ):
        assert token in recovery_host, token

    for token in (
        "build_recovery_bundle",
        "validate_signed_provisioning_policy(provisioning_policy_path)",
        "candidate_sequence = installed_sequence + 1",
        "candidate_blob[12:44] == active_blob[12:44]",
        '"signed_maintenance_authorization_required": True',
        '"automatic_recovery": False',
        '"decrement_permitted": False',
    ):
        assert token in preparer, token

    for token in (
        "verify_recovery_bundle",
        "validate_signed_provisioning_policy(provisioning_policy_path)",
        "candidate != installed + 1",
        "active_record_sha256_bound",
        "approved_profile_reverified",
        "sequence_decrement_performed",
        "hard_safety_non_regression_pass",
    ):
        assert token in verifier, token

    for token in (
        "validate_signed_provisioning_policy(args.provisioning_policy)",
        "_verify_recovery_if_present(args)",
        "RecoveryMaintenanceClient",
        "apply_recovery_aware_signed_provisioning",
        "verify_recovery_aware_reboot",
        "active_record_sha256",
        "active_record_hex",
    ):
        assert token in physical_tool, token
    assert physical_tool.index("_verify_recovery_if_present(args)") < physical_tool.index("serial_port = _serial_port")

    for token in (
        "validate_signed_provisioning_policy(args.provisioning_policy)",
        "verify_recovery_bundle(",
        '"monotonic_sequence_preserved"',
    ):
        assert token in signing_request, token

    for token in (
        "signed_maintenance_authorization_required_at_write_time",
        "cryptographic_authorization_required_for_write",
        "private_signing_key_on_device",
        "candidate_sequence_increment_exactly_one",
        "sequence_decrement_permitted",
    ):
        assert token in policy_validator, token

    recovery_policy = provisioning_policy["recovery"]
    assert recovery_policy["approved_profile_restoration_supported"] is True
    assert recovery_policy["exact_active_record_readback_required"] is True
    assert recovery_policy["candidate_sequence_increment_exactly_one"] is True
    assert recovery_policy["sequence_decrement_permitted"] is False
    assert recovery_policy["same_coefficients_noop_rejected"] is True
    assert recovery_policy["signed_maintenance_authorization_required"] is True
    assert recovery_policy["automatic_recovery"] is False

    rotation = authority_policy["rotation"]
    assert rotation["runtime_key_update_supported"] is False
    assert rotation["remote_key_update_supported"] is False
    assert rotation["dual_key_overlap_supported"] is False
    assert rotation["rotation_requires_source_review"] is True
    assert rotation["rotation_requires_maintenance_image_rebuild"] is True
    assert rotation["normal_calibration_write_may_rotate_key"] is False
    assert authority_policy["key_material"]["private_key_on_device"] is False
    assert authority_policy["authority"]["automatic_key_rotation"] is False

    for forbidden in (
        "authority_key_write",
        "rotate_authority_key",
        "set_authority_key",
        "update_authority_key",
        "sequence_decrement",
        "automatic_recovery = true",
        "may_relax_hard_safety_limits = true",
    ):
        lowered = forbidden.lower()
        assert lowered not in maintenance_app.lower(), forbidden
        assert lowered not in production_app.lower(), forbidden
        assert lowered not in transparent_bridge.lower(), forbidden

    for token in (
        "test_recovery_builder_uses_next_sequence_and_binds_exact_active_record",
        "test_recovery_builder_rejects_noop_coefficients",
        "test_active_record_query_returns_exact_blob_hash_sequence_and_crc",
        "test_runtime_recovery_binding_rejects_changed_active_record",
        "test_recovery_verifier_rejects_tampered_active_record_binding",
        "test_recovery_reboot_verification_requires_exact_record_sha",
    ):
        assert token in tests, token

    print(
        "calibration_recovery_check PASS: strict signed policy, exact active-record readback, approved-profile "
        "restoration at the next higher sequence, exact SHA recheck after reboot, signed authorization, no automatic "
        "recovery, and source-review-only authority-key rotation boundary are present"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
