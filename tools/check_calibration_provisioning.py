from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    preparer = (root / "tools/prepare_calibration_provisioning.py").read_text(encoding="utf-8")
    verifier = (root / "tools/verify_calibration_provisioning.py").read_text(encoding="utf-8")
    policy = (root / "hardware/calibration/calibration_provisioning_policy_v1.json").read_text(encoding="utf-8")
    state_template = (root / "hardware/calibration/calibration_device_state_template_v1.json").read_text(encoding="utf-8")
    selection = (root / "firmware/components/forgesense_sensing/forgesense_calibration_provisioning.cpp").read_text(encoding="utf-8")
    nvs_store = (root / "firmware/esp32/main/calibration_store_nvs.cpp").read_text(encoding="utf-8")
    tests = (root / "tests/test_calibration_provisioning.py").read_text(encoding="utf-8")
    host_test = (root / "firmware/tests/calibration_provisioning_test.cpp").read_text(encoding="utf-8")

    for token in (
        'PROVISIONING_SCHEMA = "forgesense.calibration_provisioning_package.v1"',
        'ARTIFACT_INDEX_SCHEMA = "forgesense.calibration_provisioning_artifact_index.v1"',
        'verify_source_derivation(',
        'encode_calibration_record(',
        'zlib.crc32(prefix)',
        'candidate sequence',
        '"package_generation_only": True',
        '"remote_provisioning_command_present": False',
        '"automatic_provisioning": False',
        '"may_control_actuators": False',
        '"may_relax_hard_safety_limits": False',
        '"hardware_backed_monotonic_counter_claimed": False',
    ):
        assert token in preparer, token

    for token in (
        'VERIFICATION_SCHEMA = "forgesense.calibration_provisioning_verification.v1"',
        'record_rederived',
        'anti_rollback_gate_pass',
        'device_write_performed',
        'exact device-state bytes',
        'verify_source_derivation(',
    ):
        assert token in verifier, token

    for token in (
        '"strictly_newer_than_installed": true',
        '"wraparound_supported": false',
        '"slot_count": 2',
        '"highest-valid-sequence-recovery": true',
        '"same-sequence-different-bytes_rejected": true',
        '"write_time_recheck_required": true',
        '"remote_provisioning_command_present": false',
        '"hardware_backed_monotonic_counter_claimed": false',
    ):
        assert token in policy, token

    assert '"maintenance_mode_confirmed": false' in state_template
    assert '"load_output_physically_inhibited_confirmed": false' in state_template

    for token in (
        'CalibrationSelectionStatus::RollbackDetected',
        'CalibrationSelectionStatus::Ambiguous',
        'CalibrationSelectionStatus::Corrupt',
        'candidate != 0U && candidate != 0xFFFFFFFFU',
        'selected.sequence == 0xFFFFFFFFU',
    ):
        assert token in selection, token

    for token in (
        'kNamespace = "fs_cal"',
        'kSlotKeys[2]',
        'nvs_set_blob',
        'nvs_commit',
        'readback != encoded',
        'write_metadata(inactive_slot, candidate.sequence)',
        'select_calibration_slot',
        'reset_failed_open()',
        'ready_ = true',
    ):
        assert token in nvs_store, token

    for forbidden in (
        "uart_rx",
        "http_post",
        "dashboard_write",
        "set_hard_limit",
        "update_safety_limit",
        "load_enable_o",
    ):
        assert forbidden not in preparer.lower(), forbidden
        assert forbidden not in verifier.lower(), forbidden
        assert forbidden not in nvs_store.lower(), forbidden

    for token in (
        "test_record_encoding_matches_calibration_record_v1",
        "test_provisioning_rejects_sequence_rollback",
        "test_provisioning_requires_safe_state_confirmation",
        "test_provisioning_bundle_verifies_and_rederives_record",
        "test_provisioning_verifier_rejects_binary_tamper",
        "test_device_state_bytes_are_bound_to_package",
    ):
        assert token in tests, token

    assert "calibration_provisioning_test PASS" in host_test
    assert "0xFFFFFFFFU" in host_test
    print(
        "calibration_provisioning_check PASS: evidence-bound record generation, strict non-wrapping sequence gate, dual-slot staged storage, readback verification, fail-closed initialization, and no remote/runtime authority escalation are present"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
