from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ledger = (root / "commissioning/forgesense_commission/audit_ledger.py").read_text(encoding="utf-8")
    manager = (root / "tools/manage_calibration_audit_ledger.py").read_text(encoding="utf-8")
    physical = (root / "tools/run_physical_calibration_provisioning.py").read_text(encoding="utf-8")
    tests = (root / "tests/test_calibration_audit_ledger.py").read_text(encoding="utf-8")
    production = (root / "firmware/esp32/main/app_main.cpp").read_text(encoding="utf-8")
    bridge = (root / "firmware/esp32_commissioning/main/app_main.cpp").read_text(encoding="utf-8")
    policy = json.loads(
        (root / "hardware/calibration/calibration_audit_ledger_policy_v1.json").read_text(encoding="utf-8")
    )

    for token in (
        'LEDGER_SCHEMA = "forgesense.calibration_audit_ledger.v1"',
        'ENTRY_SCHEMA = "forgesense.calibration_audit_entry.v1"',
        'GENESIS_PREVIOUS_SHA256 = "0" * 64',
        "initialize_ledger",
        "verify_ledger",
        "preflight_live_state",
        "append_write_evidence",
        "append_reboot_evidence",
        'target.open("xb")',
        "os.fsync",
        'event_type = "recovery_commit"',
        'event_type == "reboot_verified"',
        "unexpected maintenance-authority rotation",
    ):
        assert token in ledger, token

    for token in (
        '"init"',
        '"verify"',
        '"append-write"',
        '"append-reboot"',
        "initialize_ledger(",
        "append_write_evidence(",
        "append_reboot_evidence(",
    ):
        assert token in manager, token

    for token in (
        'parser.add_argument("--audit-ledger", type=Path, required=True)',
        "calibration_audit_ledger_policy_v1.json",
        "_preflight_audit_ledger(args, client)",
        "verify_ledger(",
        "preflight_live_state(",
        "append_write_evidence(",
        "append_reboot_evidence(",
        '"audit_ledger_required": True',
        '"audit_ledger_preflight_verified": True',
    ):
        assert token in physical, token
    structural_position = physical.index("pre_serial_ledger = verify_ledger(")
    serial_position = physical.index("serial_port = _serial_port", structural_position)
    assert structural_position < serial_position
    save_position = physical.index("_save_json(args.report_out, report)")
    append_position = physical.index("append_write_evidence(", save_position)
    assert save_position < append_position

    assert policy["schema"] == "forgesense.calibration_audit_ledger_policy.v1"
    assert policy["initialization"]["fresh_device_sequence_required"] == 0
    assert policy["initialization"]["active_record_must_be_absent"] is True
    assert policy["initialization"]["adopt_nonzero_history_supported"] is False
    assert policy["chain"]["hash"] == "SHA-256"
    assert policy["chain"]["head_derived_from_last_entry"] is True
    assert policy["chain"]["metadata_bound_by_genesis"] is True
    assert policy["chain"]["silent_entry_rewrite_permitted"] is False
    assert policy["write_preflight"]["ledger_required"] is True
    assert policy["write_preflight"]["live_active_record_sha256_match_required_when_active"] is True
    assert policy["write_preflight"]["live_authority_public_key_sha256_match_required"] is True
    assert policy["write_preflight"]["unexpected_authority_rotation_permitted"] is False
    assert policy["events"]["sequence_decrement_permitted"] is False
    assert policy["events"]["recovery_increment_exactly_one"] is True
    assert policy["authority"]["is_digital_signature"] is False
    assert policy["authority"]["is_immutable_storage"] is False
    assert policy["authority"]["may_control_actuators"] is False
    assert policy["authority"]["may_relax_hard_safety_limits"] is False

    for forbidden in (
        "calibration_audit_ledger",
        "append_write_evidence",
        "append_reboot_evidence",
        "audit-ledger",
    ):
        assert forbidden not in production
        assert forbidden not in bridge

    for token in (
        "test_fresh_device_genesis_and_live_preflight",
        "test_initialization_rejects_nonzero_or_active_history",
        "test_write_reboot_recovery_chain_is_contiguous",
        "test_entry_tamper_is_detected",
        "test_duplicate_or_replayed_write_evidence_is_rejected",
        "test_live_record_drift_and_signer_drift_fail_closed",
        "test_recovery_event_requires_exact_next_sequence",
        "test_genesis_metadata_tamper_is_detected",
    ):
        assert token in tests, token

    print(
        "calibration_audit_ledger_check PASS: append-structured SHA-256 history, fresh-device genesis, live exact-record "
        "and signer continuity, write/recovery/reboot evidence chaining, fail-closed tamper detection, and production "
        "authority separation are present"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
