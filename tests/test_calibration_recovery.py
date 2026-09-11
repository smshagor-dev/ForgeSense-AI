from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import zlib

import pytest

from commissioning.forgesense_commission.provisioning import (
    ARTIFACT_INDEX_SCHEMA,
    PROVISIONING_SCHEMA,
    FrameParser,
    MaintenanceProvisioningError,
    encode_frame,
)
from commissioning.forgesense_commission.recovery import (
    OP_ACTIVE_RECORD_RESPONSE,
    OP_QUERY_ACTIVE_RECORD,
    ActiveCalibrationRecord,
    RecoveryMaintenanceClient,
    validate_recovery_runtime_binding,
)
import tools.prepare_calibration_recovery as prep
import tools.verify_calibration_recovery as verify


def make_record(sequence: int, *, current_num: int = 1, current_den: int = 2000, temp_offset: int = 2) -> bytes:
    prefix = struct.pack(
        "<IHHIiiiiiiii",
        0x46534331,
        1,
        48,
        sequence,
        0,
        1,
        1,
        temp_offset,
        0,
        current_num,
        current_den,
        0,
    )
    return prefix + struct.pack("<I", zlib.crc32(prefix) & 0xFFFFFFFF)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_state(path: Path, active: bytes) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "forgesense.calibration_device_state.v1",
                "device_id": "esp32s3:aabbccddeeff",
                "captured_at_utc": "2026-09-12T00:00:00Z",
                "installed_sequence": struct.unpack_from("<I", active, 8)[0],
                "installed_record_crc32": struct.unpack_from("<I", active, 44)[0],
                "active_record_sha256": _sha256(active),
                "active_record_hex": active.hex(),
                "maintenance_mode_confirmed": True,
                "load_output_physically_inhibited_confirmed": True,
                "source": "synthetic exact maintenance readback",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def fake_generic_artifacts(sequence: int, candidate: bytes) -> dict[str, bytes]:
    package = {
        "schema": PROVISIONING_SCHEMA,
        "policy_id": "CAL-PROVISION-001",
        "device_id": "esp32s3:aabbccddeeff",
        "campaign_id": "CAL-OLD-001",
        "approval_id": "APR-OLD-001",
        "repository_commit": "f" * 40,
        "evidence_root_sha256": "a" * 64,
        "change_package_sha256": "b" * 64,
        "sequence": {"installed": sequence - 1, "candidate": sequence},
        "record": {
            "format": "CalibrationRecord-v1",
            "blob_size_bytes": 48,
            "crc32_ieee": struct.unpack_from("<I", candidate, 44)[0],
            "sha256": _sha256(candidate),
        },
        "authority": {
            "package_generation_only": True,
            "remote_provisioning_command_present": False,
            "automatic_provisioning": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
            "hardware_backed_monotonic_counter_claimed": False,
        },
    }
    provisioning = (json.dumps(package, indent=2) + "\n").encode()
    hex_bytes = (candidate.hex() + "\n").encode("ascii")
    index = {
        "schema": ARTIFACT_INDEX_SCHEMA,
        "campaign_id": package["campaign_id"],
        "device_id": package["device_id"],
        "sequence": sequence,
        "artifacts": [],
        "authority": {
            "integrity_index_only": True,
            "automatic_provisioning": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
        "root_sha256": "0" * 64,
    }
    return {
        "provisioning.json": provisioning,
        "calibration-record.bin": candidate,
        "calibration-record.hex": hex_bytes,
        "artifact-index.json": (json.dumps(index, indent=2) + "\n").encode(),
    }


def build_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, noop: bool = False) -> tuple[Path, Path, bytes]:
    active = make_record(4, current_num=3, current_den=4000, temp_offset=4)
    candidate = make_record(
        5,
        current_num=3 if noop else 1,
        current_den=4000 if noop else 2000,
        temp_offset=4 if noop else 2,
    )
    state_path = tmp_path / "device-state.json"
    write_state(state_path, active)
    source_change = tmp_path / "source-change"
    source_change.mkdir()
    (source_change / "approved-profile.json").write_text(
        json.dumps({"campaign_id": "CAL-OLD-001", "approval_id": "APR-OLD-001"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(prep, "validate_signed_provisioning_policy", lambda *args, **kwargs: {})
    monkeypatch.setattr(verify, "validate_signed_provisioning_policy", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        prep,
        "build_provisioning_bundle",
        lambda *args, **kwargs: fake_generic_artifacts(kwargs["sequence"], candidate),
    )
    return source_change, state_path, active


def test_recovery_builder_uses_next_sequence_and_binds_exact_active_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_change, state_path, active = build_fixture(tmp_path, monkeypatch)
    artifacts = prep.build_recovery_bundle(
        source_change,
        bundle_dir=tmp_path,
        change_package_dir=tmp_path,
        approval_path=tmp_path / "approval.json",
        source_root=tmp_path,
        campaign_manifest=tmp_path / "campaign.json",
        repo_root=tmp_path,
        source_change_policy_path=tmp_path / "source-policy.json",
        device_state_path=state_path,
        provisioning_policy_path=tmp_path / "provision-policy.json",
        reason="Restore the previously approved stable calibration profile",
    )
    package = json.loads(artifacts["provisioning.json"])
    intent = package["intent"]
    assert package["sequence"] == {"installed": 4, "candidate": 5}
    assert intent["from_active_record"]["sha256"] == _sha256(active)
    assert intent["sequence_semantics"]["increment_exactly_one"] is True
    assert intent["sequence_semantics"]["decrement_permitted"] is False
    assert intent["authority"]["signed_maintenance_authorization_required"] is True
    assert intent["authority"]["automatic_recovery"] is False


def test_recovery_builder_rejects_noop_coefficients(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_change, state_path, _ = build_fixture(tmp_path, monkeypatch, noop=True)
    with pytest.raises(prep.CalibrationProvisioningError, match="no-op restoration"):
        prep.build_recovery_bundle(
            source_change,
            bundle_dir=tmp_path,
            change_package_dir=tmp_path,
            approval_path=tmp_path / "approval.json",
            source_root=tmp_path,
            campaign_manifest=tmp_path / "campaign.json",
            repo_root=tmp_path,
            source_change_policy_path=tmp_path / "source-policy.json",
            device_state_path=state_path,
            provisioning_policy_path=tmp_path / "provision-policy.json",
            reason="Restore the previously approved stable calibration profile",
        )


class ActiveRecordTransport:
    def __init__(self, active: bytes) -> None:
        self.active = active
        self.parser = FrameParser()
        self.rx = bytearray()
        self.seen: list[int] = []

    def write(self, data: bytes) -> int:
        for frame in self.parser.feed(data):
            self.seen.append(frame.opcode)
            if frame.opcode != OP_QUERY_ACTIVE_RECORD:
                raise AssertionError(f"unexpected opcode {frame.opcode}")
            payload = bytes([0, 1]) + self.active
            self.rx.extend(encode_frame(OP_ACTIVE_RECORD_RESPONSE, payload))
        return len(data)

    def read(self, size: int = 1) -> bytes:
        if not self.rx:
            return b""
        count = min(size, len(self.rx))
        data = bytes(self.rx[:count])
        del self.rx[:count]
        return data


def test_active_record_query_returns_exact_blob_hash_sequence_and_crc() -> None:
    active = make_record(9, current_num=7, current_den=9000)
    transport = ActiveRecordTransport(active)
    result = RecoveryMaintenanceClient(transport, timeout_s=0.05).query_active_record()
    assert transport.seen == [OP_QUERY_ACTIVE_RECORD]
    assert result.present is True
    assert result.blob == active
    assert result.sequence == 9
    assert result.crc32_ieee == struct.unpack_from("<I", active, 44)[0]
    assert result.sha256 == _sha256(active)


def test_runtime_recovery_binding_rejects_changed_active_record() -> None:
    active = make_record(4, current_num=3)
    other = make_record(4, current_num=4)
    package = {
        "sequence": {"installed": 4, "candidate": 5},
        "intent": {
            "schema": "forgesense.calibration_recovery_intent.v1",
            "mode": "restore_approved_profile_with_new_sequence",
            "from_active_record": {
                "sequence": 4,
                "crc32_ieee": struct.unpack_from("<I", active, 44)[0],
                "sha256": _sha256(active),
            },
            "sequence_semantics": {
                "candidate_is_new_higher_sequence": True,
                "decrement_permitted": False,
            },
            "authority": {
                "signed_maintenance_authorization_required": True,
                "automatic_recovery": False,
                "may_control_actuators": False,
                "may_relax_hard_safety_limits": False,
                "hardware_backed_monotonic_counter_claimed": False,
            },
        },
    }
    observed = ActiveCalibrationRecord(
        True,
        other,
        4,
        struct.unpack_from("<I", other, 44)[0],
        _sha256(other),
    )
    with pytest.raises(MaintenanceProvisioningError, match="SHA-256 changed"):
        validate_recovery_runtime_binding(package, observed)


def test_recovery_verifier_rejects_tampered_active_record_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_change, state_path, active = build_fixture(tmp_path, monkeypatch)
    artifacts = prep.build_recovery_bundle(
        source_change,
        bundle_dir=tmp_path,
        change_package_dir=tmp_path,
        approval_path=tmp_path / "approval.json",
        source_root=tmp_path,
        campaign_manifest=tmp_path / "campaign.json",
        repo_root=tmp_path,
        source_change_policy_path=tmp_path / "source-policy.json",
        device_state_path=state_path,
        provisioning_policy_path=tmp_path / "provision-policy.json",
        reason="Restore the previously approved stable calibration profile",
    )
    out = tmp_path / "recovery"
    out.mkdir()
    for name, content in artifacts.items():
        (out / name).write_bytes(content)

    monkeypatch.setattr(
        verify,
        "verify_provisioning_bundle",
        lambda *args, **kwargs: {
            "record_rederived": True,
            "source_derivation_reverified": True,
            "hard_safety_non_regression_pass": True,
        },
    )
    result = verify.verify_recovery_bundle(
        out,
        source_change_dir=source_change,
        bundle_dir=tmp_path,
        change_package_dir=tmp_path,
        approval_path=tmp_path / "approval.json",
        source_root=tmp_path,
        campaign_manifest=tmp_path / "campaign.json",
        repo_root=tmp_path,
        source_change_policy_path=tmp_path / "source-policy.json",
        device_state_path=state_path,
        provisioning_policy_path=tmp_path / "provision-policy.json",
    )
    assert result["monotonic_sequence_preserved"] is True
    assert result["sequence_decrement_performed"] is False

    state = json.loads(state_path.read_text())
    state["active_record_sha256"] = "0" * 64
    state_path.write_text(json.dumps(state) + "\n")
    with pytest.raises(verify.CalibrationRecoveryVerificationError, match="SHA-256 mismatch"):
        verify.verify_recovery_bundle(
            out,
            source_change_dir=source_change,
            bundle_dir=tmp_path,
            change_package_dir=tmp_path,
            approval_path=tmp_path / "approval.json",
            source_root=tmp_path,
            campaign_manifest=tmp_path / "campaign.json",
            repo_root=tmp_path,
            source_change_policy_path=tmp_path / "source-policy.json",
            device_state_path=state_path,
            provisioning_policy_path=tmp_path / "provision-policy.json",
        )
