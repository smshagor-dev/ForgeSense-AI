from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import zlib

import pytest

import tools.prepare_calibration_provisioning as prep
import tools.verify_calibration_provisioning as verify

COMMIT = "f" * 40
ROOT = "a" * 64
CHANGE_PACKAGE = "b" * 64


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _profile() -> dict:
    return {
        "schema": prep.PROFILE_SCHEMA,
        "approval_id": "APR-001",
        "campaign_id": "CAL-001",
        "repository_commit": COMMIT,
        "evidence_root_sha256": ROOT,
        "change_package_sha256": CHANGE_PACKAGE,
        "calibration_record_v1_candidate": {
            "temperature": {
                "raw_zero": 0,
                "gain_numerator": 1,
                "gain_denominator": 1,
                "output_offset": 2,
            },
            "current": {
                "raw_zero": 0,
                "gain_numerator": 1,
                "gain_denominator": 2000,
                "output_offset": 0,
            },
        },
        "authority": {
            "source_review_artifact_only": True,
            "runtime_write_permitted": False,
            "automatic_runtime_application": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
    }


def _source_change() -> dict:
    return {
        "schema": prep.SOURCE_CHANGE_SCHEMA,
        "approval_id": "APR-001",
        "campaign_id": "CAL-001",
        "repository_commit": COMMIT,
        "evidence_root_sha256": ROOT,
        "change_package_sha256": CHANGE_PACKAGE,
    }


def _policy() -> dict:
    return {
        "schema": prep.POLICY_SCHEMA,
        "policy_id": "CAL-PROVISION-TEST",
        "sequence": {
            "minimum": 1,
            "maximum": 4294967294,
            "strictly_newer_than_installed": True,
            "wraparound_supported": False,
        },
        "record": {
            "format": "CalibrationRecord-v1",
            "blob_size_bytes": 48,
            "byte_order": "little-endian",
            "integrity": "CRC32/IEEE",
        },
        "storage": {
            "namespace": "fs_cal",
            "slot_count": 2,
            "strategy": "inactive-slot-write-commit-readback-then-metadata-commit",
            "highest-valid-sequence-recovery": True,
            "same-sequence-different-bytes_rejected": True,
        },
        "preconditions": {
            "maintenance_mode_confirmation_required": True,
            "load_output_physically_inhibited_confirmation_required": True,
            "write_time_recheck_required": True,
        },
        "authority": {
            "remote_provisioning_command_present": False,
            "automatic_provisioning": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
            "hardware_backed_monotonic_counter_claimed": False,
        },
    }


def _state(installed_sequence: int = 4) -> dict:
    return {
        "schema": prep.DEVICE_STATE_SCHEMA,
        "device_id": "SYNTHETIC-DEVICE-001",
        "captured_at_utc": "2026-09-11T19:00:00Z",
        "installed_sequence": installed_sequence,
        "installed_record_crc32": None,
        "maintenance_mode_confirmed": True,
        "load_output_physically_inhibited_confirmed": True,
        "source": "synthetic test fixture",
    }


def _derivation() -> dict:
    return {
        "schema": "forgesense.calibration_source_derivation_verification.v1",
        "reviewer_package_rederived": True,
        "approval_semantics_revalidated": True,
        "current_coefficients_rederived": True,
        "temperature_coefficients_rederived": True,
        "hard_safety_non_regression_pass": True,
        "runtime_source_unchanged": True,
    }


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, installed_sequence: int = 4) -> dict[str, Path]:
    source_change_dir = tmp_path / "source-change"
    source_change_dir.mkdir()
    (source_change_dir / "approved-profile.json").write_bytes(_json_bytes(_profile()))
    (source_change_dir / "source-change.json").write_bytes(_json_bytes(_source_change()))

    device_state = tmp_path / "device-state.json"
    device_state.write_bytes(_json_bytes(_state(installed_sequence)))
    provisioning_policy = tmp_path / "provisioning-policy.json"
    provisioning_policy.write_bytes(_json_bytes(_policy()))

    placeholder = tmp_path / "placeholder.json"
    placeholder.write_text("{}\n", encoding="utf-8")
    placeholder_dir = tmp_path / "placeholder-dir"
    placeholder_dir.mkdir()

    monkeypatch.setattr(prep, "verify_source_derivation", lambda *args, **kwargs: _derivation())
    monkeypatch.setattr(verify, "verify_source_derivation", lambda *args, **kwargs: _derivation())

    return {
        "source_change_dir": source_change_dir,
        "device_state": device_state,
        "provisioning_policy": provisioning_policy,
        "placeholder": placeholder,
        "placeholder_dir": placeholder_dir,
    }


def _build(paths: dict[str, Path], sequence: int) -> dict[str, bytes]:
    return prep.build_provisioning_bundle(
        paths["source_change_dir"],
        bundle_dir=paths["placeholder_dir"],
        change_package_dir=paths["placeholder_dir"],
        approval_path=paths["placeholder"],
        source_root=paths["placeholder_dir"],
        campaign_manifest=paths["placeholder"],
        repo_root=paths["placeholder_dir"],
        source_change_policy_path=paths["placeholder"],
        device_state_path=paths["device_state"],
        provisioning_policy_path=paths["provisioning_policy"],
        sequence=sequence,
    )


def test_record_encoding_matches_calibration_record_v1() -> None:
    profile = _profile()
    blob = prep.encode_calibration_record(profile, 5)
    assert len(blob) == 48
    magic, version, size, sequence = struct.unpack_from("<IHHI", blob, 0)
    assert magic == prep.CAL_MAGIC
    assert version == 1
    assert size == 48
    assert sequence == 5
    assert struct.unpack_from("<iiii", blob, 12) == (0, 1, 1, 2)
    assert struct.unpack_from("<iiii", blob, 28) == (0, 1, 2000, 0)
    expected_crc = zlib.crc32(blob[:44]) & 0xFFFFFFFF
    assert struct.unpack_from("<I", blob, 44)[0] == expected_crc


def test_provisioning_rejects_sequence_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _fixture(tmp_path, monkeypatch, installed_sequence=7)
    with pytest.raises(prep.CalibrationProvisioningError, match="not newer than installed sequence"):
        _build(paths, sequence=7)
    with pytest.raises(prep.CalibrationProvisioningError, match="not newer than installed sequence"):
        _build(paths, sequence=6)


def test_provisioning_requires_safe_state_confirmation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _fixture(tmp_path, monkeypatch)
    state = _state()
    state["maintenance_mode_confirmed"] = False
    paths["device_state"].write_bytes(_json_bytes(state))
    with pytest.raises(prep.CalibrationProvisioningError, match="maintenance mode"):
        _build(paths, sequence=5)


def test_provisioning_bundle_verifies_and_rederives_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _fixture(tmp_path, monkeypatch)
    artifacts = _build(paths, sequence=5)
    provisioning_dir = tmp_path / "provisioning"
    provisioning_dir.mkdir()
    for relative, content in artifacts.items():
        (provisioning_dir / relative).write_bytes(content)

    result = verify.verify_provisioning_bundle(
        provisioning_dir,
        source_change_dir=paths["source_change_dir"],
        bundle_dir=paths["placeholder_dir"],
        change_package_dir=paths["placeholder_dir"],
        approval_path=paths["placeholder"],
        source_root=paths["placeholder_dir"],
        campaign_manifest=paths["placeholder"],
        repo_root=paths["placeholder_dir"],
        source_change_policy_path=paths["placeholder"],
        device_state_path=paths["device_state"],
        provisioning_policy_path=paths["provisioning_policy"],
    )
    assert result["record_rederived"] is True
    assert result["anti_rollback_gate_pass"] is True
    assert result["device_write_performed"] is False
    assert result["hard_safety_non_regression_pass"] is True


def test_provisioning_verifier_rejects_binary_tamper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _fixture(tmp_path, monkeypatch)
    artifacts = _build(paths, sequence=5)
    provisioning_dir = tmp_path / "provisioning"
    provisioning_dir.mkdir()
    for relative, content in artifacts.items():
        (provisioning_dir / relative).write_bytes(content)
    blob = bytearray((provisioning_dir / "calibration-record.bin").read_bytes())
    blob[16] ^= 0x01
    (provisioning_dir / "calibration-record.bin").write_bytes(blob)
    with pytest.raises(verify.CalibrationProvisioningVerificationError, match="artifact hash mismatch"):
        verify.verify_provisioning_bundle(
            provisioning_dir,
            source_change_dir=paths["source_change_dir"],
            bundle_dir=paths["placeholder_dir"],
            change_package_dir=paths["placeholder_dir"],
            approval_path=paths["placeholder"],
            source_root=paths["placeholder_dir"],
            campaign_manifest=paths["placeholder"],
            repo_root=paths["placeholder_dir"],
            source_change_policy_path=paths["placeholder"],
            device_state_path=paths["device_state"],
            provisioning_policy_path=paths["provisioning_policy"],
        )


def test_device_state_bytes_are_bound_to_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _fixture(tmp_path, monkeypatch)
    artifacts = _build(paths, sequence=5)
    provisioning_dir = tmp_path / "provisioning"
    provisioning_dir.mkdir()
    for relative, content in artifacts.items():
        (provisioning_dir / relative).write_bytes(content)
    state = _state()
    state["source"] = "changed after package creation"
    paths["device_state"].write_bytes(_json_bytes(state))
    with pytest.raises(verify.CalibrationProvisioningVerificationError, match="exact device-state bytes"):
        verify.verify_provisioning_bundle(
            provisioning_dir,
            source_change_dir=paths["source_change_dir"],
            bundle_dir=paths["placeholder_dir"],
            change_package_dir=paths["placeholder_dir"],
            approval_path=paths["placeholder"],
            source_root=paths["placeholder_dir"],
            campaign_manifest=paths["placeholder"],
            repo_root=paths["placeholder_dir"],
            source_change_policy_path=paths["placeholder"],
            device_state_path=paths["device_state"],
            provisioning_policy_path=paths["provisioning_policy"],
        )
