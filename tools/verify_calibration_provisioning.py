from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

try:
    from tools.prepare_calibration_provisioning import (
        ARTIFACT_INDEX_SCHEMA,
        DEVICE_STATE_SCHEMA,
        POLICY_SCHEMA,
        PROFILE_SCHEMA,
        PROVISIONING_SCHEMA,
        CalibrationProvisioningError,
        _canonical_sha256,
        _load_json,
        _sha256_bytes,
        _validate_device_state,
        _validate_policy,
        encode_calibration_record,
    )
    from tools.verify_calibration_source_derivation import (
        CalibrationSourceDerivationError,
        verify_source_derivation,
    )
except ModuleNotFoundError:  # Direct execution from repository root.
    from prepare_calibration_provisioning import (
        ARTIFACT_INDEX_SCHEMA,
        DEVICE_STATE_SCHEMA,
        POLICY_SCHEMA,
        PROFILE_SCHEMA,
        PROVISIONING_SCHEMA,
        CalibrationProvisioningError,
        _canonical_sha256,
        _load_json,
        _sha256_bytes,
        _validate_device_state,
        _validate_policy,
        encode_calibration_record,
    )
    from verify_calibration_source_derivation import CalibrationSourceDerivationError, verify_source_derivation

VERIFICATION_SCHEMA = "forgesense.calibration_provisioning_verification.v1"
EXPECTED_ARTIFACTS = {
    "provisioning.json",
    "calibration-record.bin",
    "calibration-record.hex",
}


class CalibrationProvisioningVerificationError(ValueError):
    pass


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError as exc:
        raise CalibrationProvisioningVerificationError(f"required file not found: {path}") from exc
    return digest.hexdigest()


def verify_provisioning_bundle(
    provisioning_dir: Path,
    *,
    source_change_dir: Path,
    bundle_dir: Path,
    change_package_dir: Path,
    approval_path: Path,
    source_root: Path,
    campaign_manifest: Path,
    repo_root: Path,
    source_change_policy_path: Path,
    device_state_path: Path,
    provisioning_policy_path: Path,
) -> dict:
    provisioning_dir = provisioning_dir.resolve()
    package = _load_json(provisioning_dir / "provisioning.json", "provisioning package")
    index = _load_json(provisioning_dir / "artifact-index.json", "provisioning artifact index")
    if package.get("schema") != PROVISIONING_SCHEMA:
        raise CalibrationProvisioningVerificationError("unsupported provisioning package schema")
    if index.get("schema") != ARTIFACT_INDEX_SCHEMA:
        raise CalibrationProvisioningVerificationError("unsupported provisioning artifact-index schema")

    claimed_root = str(index.get("root_sha256", ""))
    index_core = {key: value for key, value in index.items() if key != "root_sha256"}
    if _canonical_sha256(index_core) != claimed_root:
        raise CalibrationProvisioningVerificationError("provisioning artifact-index root mismatch")

    entries = index.get("artifacts")
    if not isinstance(entries, list):
        raise CalibrationProvisioningVerificationError("provisioning artifact index has no artifacts")
    indexed: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise CalibrationProvisioningVerificationError("provisioning artifact entry is invalid")
        path = str(entry.get("path", ""))
        if path in indexed or path not in EXPECTED_ARTIFACTS:
            raise CalibrationProvisioningVerificationError("provisioning artifact set is invalid")
        indexed.add(path)
        if _file_sha256(provisioning_dir / path) != str(entry.get("sha256", "")):
            raise CalibrationProvisioningVerificationError(f"provisioning artifact hash mismatch: {path}")
    if indexed != EXPECTED_ARTIFACTS:
        raise CalibrationProvisioningVerificationError("provisioning artifact set is incomplete")
    actual = {
        path.name
        for path in provisioning_dir.iterdir()
        if path.is_file() and path.name != "artifact-index.json"
    }
    if actual != EXPECTED_ARTIFACTS:
        raise CalibrationProvisioningVerificationError("provisioning directory contains unexpected or missing files")

    policy = _load_json(provisioning_policy_path, "provisioning policy")
    state = _load_json(device_state_path, "device state")
    try:
        _validate_policy(policy)
        installed_sequence = _validate_device_state(state, policy)
    except CalibrationProvisioningError as exc:
        raise CalibrationProvisioningVerificationError(f"policy/device-state validation failed: {exc}") from exc

    source_change_dir = source_change_dir.resolve()
    try:
        derivation = verify_source_derivation(
            source_change_dir,
            bundle_dir=bundle_dir,
            change_package_dir=change_package_dir,
            approval_path=approval_path,
            source_root=source_root,
            campaign_manifest=campaign_manifest,
            repo_root=repo_root,
            policy_path=source_change_policy_path,
        )
    except CalibrationSourceDerivationError as exc:
        raise CalibrationProvisioningVerificationError(f"source derivation verification failed: {exc}") from exc

    profile_path = source_change_dir / "approved-profile.json"
    profile = _load_json(profile_path, "approved calibration profile")
    if profile.get("schema") != PROFILE_SCHEMA:
        raise CalibrationProvisioningVerificationError("unsupported approved calibration profile schema")

    sequence = package.get("sequence")
    if not isinstance(sequence, dict):
        raise CalibrationProvisioningVerificationError("provisioning sequence section is missing")
    candidate = int(sequence.get("candidate", -1))
    if int(sequence.get("installed", -1)) != installed_sequence:
        raise CalibrationProvisioningVerificationError("provisioning installed sequence differs from device-state input")
    if candidate <= installed_sequence:
        raise CalibrationProvisioningVerificationError("provisioning candidate sequence is not newer than installed sequence")
    if candidate < int(policy["sequence"]["minimum"]) or candidate > int(policy["sequence"]["maximum"]):
        raise CalibrationProvisioningVerificationError("provisioning candidate sequence is outside policy bounds")

    try:
        expected_blob = encode_calibration_record(profile, candidate)
    except CalibrationProvisioningError as exc:
        raise CalibrationProvisioningVerificationError(f"record re-encoding failed: {exc}") from exc
    retained_blob = (provisioning_dir / "calibration-record.bin").read_bytes()
    if retained_blob != expected_blob:
        raise CalibrationProvisioningVerificationError("calibration record binary differs from evidence-derived profile")
    expected_hex = expected_blob.hex() + "\n"
    if (provisioning_dir / "calibration-record.hex").read_text(encoding="ascii") != expected_hex:
        raise CalibrationProvisioningVerificationError("calibration record hex differs from binary record")

    record = package.get("record")
    if not isinstance(record, dict):
        raise CalibrationProvisioningVerificationError("provisioning record metadata is missing")
    expected_crc = struct.unpack_from("<I", expected_blob, 44)[0]
    if int(record.get("crc32_ieee", -1)) != expected_crc:
        raise CalibrationProvisioningVerificationError("provisioning record CRC metadata is invalid")
    if record.get("sha256") != _sha256_bytes(expected_blob):
        raise CalibrationProvisioningVerificationError("provisioning record SHA-256 metadata is invalid")
    if int(record.get("blob_size_bytes", 0)) != len(expected_blob):
        raise CalibrationProvisioningVerificationError("provisioning record size metadata is invalid")

    if package.get("device_id") != state.get("device_id"):
        raise CalibrationProvisioningVerificationError("provisioning device_id differs from device state")
    if package.get("device_state_sha256") != _file_sha256(device_state_path):
        raise CalibrationProvisioningVerificationError("provisioning package is not bound to exact device-state bytes")
    if package.get("approved_profile_sha256") != _file_sha256(profile_path):
        raise CalibrationProvisioningVerificationError("provisioning package is not bound to exact approved profile bytes")
    for field in ("campaign_id", "repository_commit", "approval_id", "evidence_root_sha256", "change_package_sha256"):
        if package.get(field) != profile.get(field):
            raise CalibrationProvisioningVerificationError(f"provisioning/profile provenance mismatch for {field}")

    preconditions = package.get("preconditions")
    if not isinstance(preconditions, dict):
        raise CalibrationProvisioningVerificationError("provisioning preconditions are missing")
    if preconditions.get("write_time_recheck_required") is not True:
        raise CalibrationProvisioningVerificationError("write-time precondition recheck is not required")
    authority = package.get("authority")
    expected_authority = {
        "package_generation_only": True,
        "remote_provisioning_command_present": False,
        "automatic_provisioning": False,
        "may_control_actuators": False,
        "may_relax_hard_safety_limits": False,
        "hardware_backed_monotonic_counter_claimed": False,
    }
    if not isinstance(authority, dict) or any(authority.get(k) is not v for k, v in expected_authority.items()):
        raise CalibrationProvisioningVerificationError("provisioning package authority boundary is invalid")

    source_status = package.get("source_derivation_verification")
    required_source_flags = (
        "reviewer_package_rederived",
        "approval_semantics_revalidated",
        "current_coefficients_rederived",
        "temperature_coefficients_rederived",
        "hard_safety_non_regression_pass",
    )
    if not isinstance(source_status, dict) or any(source_status.get(key) is not True for key in required_source_flags):
        raise CalibrationProvisioningVerificationError("provisioning package lacks full source-derivation verification")
    if derivation.get("runtime_source_unchanged") is not True:
        raise CalibrationProvisioningVerificationError("source derivation did not preserve runtime-source boundary")

    return {
        "schema": VERIFICATION_SCHEMA,
        "campaign_id": package["campaign_id"],
        "device_id": package["device_id"],
        "sequence": candidate,
        "artifact_integrity_pass": True,
        "record_rederived": True,
        "source_derivation_reverified": True,
        "anti_rollback_gate_pass": True,
        "write_time_recheck_required": True,
        "device_write_performed": False,
        "hard_safety_non_regression_pass": True,
        "authority": {
            "verification_only": True,
            "automatic_provisioning": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
            "hardware_backed_monotonic_counter_claimed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a ForgeSense calibration provisioning package without writing a device")
    parser.add_argument("provisioning_dir", type=Path)
    parser.add_argument("--source-change-dir", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--change-package-dir", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--campaign-manifest", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--source-change-policy", type=Path, default=Path("hardware/calibration/calibration_source_change_policy_v1.json"))
    parser.add_argument("--device-state", type=Path, required=True)
    parser.add_argument("--provisioning-policy", type=Path, default=Path("hardware/calibration/calibration_provisioning_policy_v1.json"))
    parser.add_argument("--report-out", type=Path)
    args = parser.parse_args()
    try:
        result = verify_provisioning_bundle(
            args.provisioning_dir,
            source_change_dir=args.source_change_dir,
            bundle_dir=args.bundle,
            change_package_dir=args.change_package_dir,
            approval_path=args.approval,
            source_root=args.source_root,
            campaign_manifest=args.campaign_manifest,
            repo_root=args.repo_root,
            source_change_policy_path=args.source_change_policy,
            device_state_path=args.device_state,
            provisioning_policy_path=args.provisioning_policy,
        )
    except CalibrationProvisioningVerificationError as exc:
        raise SystemExit(f"calibration provisioning verification failed: {exc}") from exc
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        "calibration provisioning verification PASS: "
        f"sequence={result['sequence']} record_rederived={result['record_rederived']} device_write_performed=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
