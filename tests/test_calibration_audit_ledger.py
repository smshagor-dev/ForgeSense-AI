from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from commissioning.forgesense_commission.audit_ledger import (
    CalibrationAuditLedgerError,
    append_reboot_evidence,
    append_write_evidence,
    initialize_ledger,
    preflight_live_state,
    verify_ledger,
)

POLICY = Path("hardware/calibration/calibration_audit_ledger_policy_v1.json")
DEVICE_ID = "esp32s3:aabbccddeeff"
AUTHORITY_SHA = "1" * 64
RECORD1_SHA = "2" * 64
RECORD2_SHA = "3" * 64
CRC = 0x12345678


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def device_state(*, sequence: int = 0, record_sha: str | None = None) -> dict:
    return {
        "schema": "forgesense.calibration_device_state.v1",
        "device_id": DEVICE_ID,
        "captured_at_utc": "2026-09-12T01:00:00Z",
        "installed_sequence": sequence,
        "installed_record_crc32": None if sequence == 0 else CRC,
        "active_record_sha256": record_sha,
        "active_record_hex": None if sequence == 0 else "00" * 48,
        "maintenance_mode_confirmed": True,
        "load_output_physically_inhibited_confirmed": True,
        "maintenance_authorization_ready": True,
        "maintenance_authority_public_key_sha256": AUTHORITY_SHA,
        "source": "synthetic exact maintenance readback",
    }


def physical_write_report(
    *,
    from_sequence: int,
    to_sequence: int,
    record_sha: str,
    recovery: bool = False,
) -> dict:
    report = {
        "schema": "forgesense.calibration_physical_provisioning.v1",
        "timestamp_utc": "2026-09-12T01:05:00Z",
        "operator": "Synthetic Operator",
        "provisioning": {
            "artifact_index_root_sha256": "4" * 64,
            "provisioning_json_sha256": "5" * 64,
            "record_sha256": record_sha,
            "candidate_sequence": to_sequence,
            "candidate_crc32_ieee": CRC,
        },
        "authorization": {
            "schema": "forgesense.calibration_maintenance_authorization.v1",
            "payload_sha256": "6" * 64,
            "signature_sha256": "7" * 64,
            "signature_format": "ECDSA-P256-SHA256-DER",
            "authority_public_key_sha256": AUTHORITY_SHA,
            "host_signature_verification": True,
            "device_signature_verification_confirmed_by_prepare": True,
        },
        "device": {"device_id": DEVICE_ID, "boot_nonce": 1001},
        "observations": {
            "pre_write": {"installed_sequence": from_sequence},
            "post_write": {"installed_sequence": to_sequence},
            "post_write_exact_active_record": {
                "present": True,
                "sequence": to_sequence,
                "crc32_ieee": CRC,
                "sha256": record_sha,
                "record_hex": "aa" * 48,
            },
        },
        "commit_verified": True,
        "reboot_recovery_verified": False,
    }
    if recovery:
        report["recovery"] = {
            "intent_schema": "forgesense.calibration_recovery_intent.v1",
            "monotonic_sequence_preserved": True,
            "sequence_decrement_performed": False,
        }
    return report


def bind_preflight(report: dict, ledger: Path) -> dict:
    state = verify_ledger(ledger, policy_path=POLICY)
    report["host_verification"] = {
        "audit_ledger_required": True,
        "audit_ledger_preflight_verified": True,
        "audit_ledger_head_before_operation": state.head_sha256,
        "audit_ledger_entry_count_before_operation": state.entry_count,
    }
    return report


def reboot_report(write_report: dict, ledger: Path) -> dict:
    report = copy.deepcopy(write_report)
    record_sha = report["provisioning"]["record_sha256"]
    sequence = report["provisioning"]["candidate_sequence"]
    report["reboot_recovery_verified"] = True
    report["reboot_verification"] = {
        "timestamp_utc": "2026-09-12T01:10:00Z",
        "previous_boot_nonce": 1001,
        "observed_boot_nonce": 2002,
        "boot_nonce_changed": True,
        "sequence_match": True,
        "crc_match": True,
        "active_record_sha256": record_sha,
        "exact_record_sha256_match": True,
        "exact_active_record": {
            "present": True,
            "sequence": sequence,
            "crc32_ieee": CRC,
            "sha256": record_sha,
            "record_hex": "aa" * 48,
        },
    }
    return bind_preflight(report, ledger)


def init_ledger(tmp_path: Path) -> tuple[Path, Path]:
    state_path = tmp_path / "device-state.json"
    write_json(state_path, device_state())
    ledger = tmp_path / "ledger"
    state = initialize_ledger(ledger, device_state_path=state_path, policy_path=POLICY)
    assert state.sequence == 0
    assert state.record_sha256 is None
    assert state.entry_count == 1
    assert state.authority_public_key_sha256 == AUTHORITY_SHA
    return ledger, state_path


def test_fresh_device_genesis_and_live_preflight(tmp_path: Path) -> None:
    ledger, _ = init_ledger(tmp_path)
    verified = verify_ledger(ledger, policy_path=POLICY, expected_device_id=DEVICE_ID)
    live = preflight_live_state(
        ledger,
        policy_path=POLICY,
        device_id=DEVICE_ID,
        installed_sequence=0,
        active_record_sha256=None,
        authority_public_key_sha256=AUTHORITY_SHA,
    )
    assert live == verified
    assert len(verified.head_sha256) == 64


def test_initialization_rejects_nonzero_or_active_history(tmp_path: Path) -> None:
    state_path = tmp_path / "device-state.json"
    write_json(state_path, device_state(sequence=4, record_sha=RECORD1_SHA))
    with pytest.raises(CalibrationAuditLedgerError, match="sequence zero"):
        initialize_ledger(tmp_path / "ledger", device_state_path=state_path, policy_path=POLICY)


def test_write_reboot_recovery_chain_is_contiguous(tmp_path: Path) -> None:
    ledger, _ = init_ledger(tmp_path)

    write1_path = tmp_path / "write-1.json"
    write1 = bind_preflight(
        physical_write_report(from_sequence=0, to_sequence=1, record_sha=RECORD1_SHA),
        ledger,
    )
    write_json(write1_path, write1)
    state1 = append_write_evidence(ledger, evidence_path=write1_path, policy_path=POLICY)
    assert state1.sequence == 1
    assert state1.record_sha256 == RECORD1_SHA
    assert state1.entry_count == 2

    reboot1_path = tmp_path / "reboot-1.json"
    write_json(reboot1_path, reboot_report(write1, ledger))
    rebooted = append_reboot_evidence(ledger, evidence_path=reboot1_path, policy_path=POLICY)
    assert rebooted.sequence == 1
    assert rebooted.record_sha256 == RECORD1_SHA
    assert rebooted.entry_count == 3

    recovery_path = tmp_path / "recovery.json"
    recovery = bind_preflight(
        physical_write_report(from_sequence=1, to_sequence=2, record_sha=RECORD2_SHA, recovery=True),
        ledger,
    )
    write_json(recovery_path, recovery)
    recovered = append_write_evidence(ledger, evidence_path=recovery_path, policy_path=POLICY)
    assert recovered.sequence == 2
    assert recovered.record_sha256 == RECORD2_SHA
    assert recovered.entry_count == 4
    assert verify_ledger(ledger, policy_path=POLICY) == recovered


def test_entry_tamper_is_detected(tmp_path: Path) -> None:
    ledger, _ = init_ledger(tmp_path)
    evidence = tmp_path / "write.json"
    report = bind_preflight(
        physical_write_report(from_sequence=0, to_sequence=1, record_sha=RECORD1_SHA),
        ledger,
    )
    write_json(evidence, report)
    append_write_evidence(ledger, evidence_path=evidence, policy_path=POLICY)
    entry_path = ledger / "00000001.json"
    entry = json.loads(entry_path.read_text(encoding="utf-8"))
    entry["state_after"]["sequence"] = 9
    write_json(entry_path, entry)
    with pytest.raises(CalibrationAuditLedgerError, match="entry hash mismatch"):
        verify_ledger(ledger, policy_path=POLICY)


def test_duplicate_or_replayed_write_evidence_is_rejected(tmp_path: Path) -> None:
    ledger, _ = init_ledger(tmp_path)
    evidence = tmp_path / "write.json"
    report = bind_preflight(
        physical_write_report(from_sequence=0, to_sequence=1, record_sha=RECORD1_SHA),
        ledger,
    )
    write_json(evidence, report)
    append_write_evidence(ledger, evidence_path=evidence, policy_path=POLICY)
    with pytest.raises(CalibrationAuditLedgerError, match="head does not match"):
        append_write_evidence(ledger, evidence_path=evidence, policy_path=POLICY)


def test_legacy_evidence_without_preflight_binding_is_rejected(tmp_path: Path) -> None:
    ledger, _ = init_ledger(tmp_path)
    evidence = tmp_path / "legacy-write.json"
    write_json(evidence, physical_write_report(from_sequence=0, to_sequence=1, record_sha=RECORD1_SHA))
    with pytest.raises(CalibrationAuditLedgerError, match="host preflight binding"):
        append_write_evidence(ledger, evidence_path=evidence, policy_path=POLICY)


def test_live_record_drift_and_signer_drift_fail_closed(tmp_path: Path) -> None:
    ledger, _ = init_ledger(tmp_path)
    evidence = tmp_path / "write.json"
    report = bind_preflight(
        physical_write_report(from_sequence=0, to_sequence=1, record_sha=RECORD1_SHA),
        ledger,
    )
    write_json(evidence, report)
    append_write_evidence(ledger, evidence_path=evidence, policy_path=POLICY)
    with pytest.raises(CalibrationAuditLedgerError, match="CalibrationRecord SHA-256 differs"):
        preflight_live_state(
            ledger,
            policy_path=POLICY,
            device_id=DEVICE_ID,
            installed_sequence=1,
            active_record_sha256="9" * 64,
            authority_public_key_sha256=AUTHORITY_SHA,
        )
    with pytest.raises(CalibrationAuditLedgerError, match="authority fingerprint differs"):
        preflight_live_state(
            ledger,
            policy_path=POLICY,
            device_id=DEVICE_ID,
            installed_sequence=1,
            active_record_sha256=RECORD1_SHA,
            authority_public_key_sha256="8" * 64,
        )


def test_recovery_event_requires_exact_next_sequence(tmp_path: Path) -> None:
    ledger, _ = init_ledger(tmp_path)
    first = tmp_path / "first.json"
    first_report = bind_preflight(
        physical_write_report(from_sequence=0, to_sequence=1, record_sha=RECORD1_SHA),
        ledger,
    )
    write_json(first, first_report)
    append_write_evidence(ledger, evidence_path=first, policy_path=POLICY)
    bad = tmp_path / "bad-recovery.json"
    bad_report = bind_preflight(
        physical_write_report(from_sequence=1, to_sequence=3, record_sha=RECORD2_SHA, recovery=True),
        ledger,
    )
    write_json(bad, bad_report)
    with pytest.raises(CalibrationAuditLedgerError, match="exactly the next"):
        append_write_evidence(ledger, evidence_path=bad, policy_path=POLICY)


def test_exact_post_write_record_is_required(tmp_path: Path) -> None:
    ledger, _ = init_ledger(tmp_path)
    evidence = tmp_path / "write.json"
    report = bind_preflight(
        physical_write_report(from_sequence=0, to_sequence=1, record_sha=RECORD1_SHA),
        ledger,
    )
    report["observations"].pop("post_write_exact_active_record")
    write_json(evidence, report)
    with pytest.raises(CalibrationAuditLedgerError, match="exact pre/post"):
        append_write_evidence(ledger, evidence_path=evidence, policy_path=POLICY)


def test_genesis_metadata_tamper_is_detected(tmp_path: Path) -> None:
    ledger, _ = init_ledger(tmp_path)
    metadata_path = ledger / "ledger.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["device_id"] = "esp32s3:ffffffffffff"
    write_json(metadata_path, metadata)
    with pytest.raises(CalibrationAuditLedgerError):
        verify_ledger(ledger, policy_path=POLICY)
