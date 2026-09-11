from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile

try:
    from tools.prepare_calibration_provisioning import (
        ARTIFACT_INDEX_SCHEMA,
        CalibrationProvisioningError,
        _canonical_sha256,
        _file_sha256,
        _json_bytes,
        _load_json,
        _sha256_bytes,
        build_provisioning_bundle,
    )
    from tools.validate_signed_provisioning_policy import (
        SignedProvisioningPolicyError,
        validate_signed_provisioning_policy,
    )
except ModuleNotFoundError:
    from prepare_calibration_provisioning import (  # type: ignore
        ARTIFACT_INDEX_SCHEMA,
        CalibrationProvisioningError,
        _canonical_sha256,
        _file_sha256,
        _json_bytes,
        _load_json,
        _sha256_bytes,
        build_provisioning_bundle,
    )
    from validate_signed_provisioning_policy import (  # type: ignore
        SignedProvisioningPolicyError,
        validate_signed_provisioning_policy,
    )

RECOVERY_INTENT_SCHEMA = "forgesense.calibration_recovery_intent.v1"
CALIBRATION_RECORD_SIZE = 48


def _decode_active_record(state: dict) -> bytes:
    text = state.get("active_record_hex")
    if not isinstance(text, str) or len(text) != CALIBRATION_RECORD_SIZE * 2:
        raise CalibrationProvisioningError(
            "recovery requires device_state.active_record_hex from the signed maintenance status capture"
        )
    try:
        blob = bytes.fromhex(text)
    except ValueError as exc:
        raise CalibrationProvisioningError("device_state.active_record_hex is not valid hexadecimal") from exc
    if len(blob) != CALIBRATION_RECORD_SIZE:
        raise CalibrationProvisioningError("device_state active record is not 48 bytes")
    sequence = struct.unpack_from("<I", blob, 8)[0]
    crc = struct.unpack_from("<I", blob, 44)[0]
    if sequence != int(state.get("installed_sequence", -1)):
        raise CalibrationProvisioningError("device-state active record sequence differs from installed sequence")
    if crc != int(state.get("installed_record_crc32", -1)):
        raise CalibrationProvisioningError("device-state active record CRC differs from installed CRC")
    claimed_sha = state.get("active_record_sha256")
    actual_sha = hashlib.sha256(blob).hexdigest()
    if claimed_sha != actual_sha:
        raise CalibrationProvisioningError("device-state active record SHA-256 is invalid")
    return blob


def _reindex(artifacts: dict[str, bytes], package: dict) -> dict[str, bytes]:
    retained = {name: content for name, content in artifacts.items() if name != "artifact-index.json"}
    retained["provisioning.json"] = _json_bytes(package)
    index_core = {
        "schema": ARTIFACT_INDEX_SCHEMA,
        "campaign_id": package["campaign_id"],
        "device_id": package["device_id"],
        "sequence": package["sequence"]["candidate"],
        "artifacts": [
            {"path": path, "sha256": _sha256_bytes(content)}
            for path, content in sorted(retained.items())
        ],
        "authority": {
            "integrity_index_only": True,
            "automatic_provisioning": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
    }
    index = dict(index_core)
    index["root_sha256"] = _canonical_sha256(index_core)
    retained["artifact-index.json"] = _json_bytes(index)
    return retained


def build_recovery_bundle(
    source_change_dir: Path,
    *,
    bundle_dir: Path,
    change_package_dir: Path,
    approval_path: Path,
    source_root: Path,
    campaign_manifest: Path,
    repo_root: Path,
    source_change_policy_path: Path,
    device_state_path: Path,
    provisioning_policy_path: Path,
    reason: str,
) -> dict[str, bytes]:
    try:
        validate_signed_provisioning_policy(provisioning_policy_path)
    except SignedProvisioningPolicyError as exc:
        raise CalibrationProvisioningError(f"signed provisioning policy validation failed: {exc}") from exc

    reason = reason.strip()
    if len(reason) < 12:
        raise CalibrationProvisioningError("recovery reason must contain at least 12 non-whitespace characters")

    state = _load_json(device_state_path, "calibration device state")
    active_blob = _decode_active_record(state)
    installed_sequence = int(state["installed_sequence"])
    if installed_sequence <= 0 or installed_sequence >= 0xFFFFFFFE:
        raise CalibrationProvisioningError("recovery cannot allocate the next non-wrapping calibration sequence")
    candidate_sequence = installed_sequence + 1

    artifacts = build_provisioning_bundle(
        source_change_dir,
        bundle_dir=bundle_dir,
        change_package_dir=change_package_dir,
        approval_path=approval_path,
        source_root=source_root,
        campaign_manifest=campaign_manifest,
        repo_root=repo_root,
        source_change_policy_path=source_change_policy_path,
        device_state_path=device_state_path,
        provisioning_policy_path=provisioning_policy_path,
        sequence=candidate_sequence,
    )
    package = json.loads(artifacts["provisioning.json"].decode("utf-8"))
    candidate_blob = artifacts["calibration-record.bin"]
    if len(candidate_blob) != CALIBRATION_RECORD_SIZE:
        raise CalibrationProvisioningError("generated recovery record is not 48 bytes")
    if candidate_blob[12:44] == active_blob[12:44]:
        raise CalibrationProvisioningError(
            "recovery target coefficients equal the currently active coefficients; no-op restoration is rejected"
        )

    profile_path = source_change_dir.resolve() / "approved-profile.json"
    intent = {
        "schema": RECOVERY_INTENT_SCHEMA,
        "mode": "restore_approved_profile_with_new_sequence",
        "reason": reason,
        "from_active_record": {
            "sequence": installed_sequence,
            "crc32_ieee": struct.unpack_from("<I", active_blob, 44)[0],
            "sha256": hashlib.sha256(active_blob).hexdigest(),
        },
        "to_approved_profile": {
            "campaign_id": package["campaign_id"],
            "approval_id": package["approval_id"],
            "approved_profile_sha256": _file_sha256(profile_path),
            "candidate_record_sha256": hashlib.sha256(candidate_blob).hexdigest(),
        },
        "sequence_semantics": {
            "installed": installed_sequence,
            "candidate": candidate_sequence,
            "candidate_is_new_higher_sequence": True,
            "decrement_permitted": False,
            "increment_exactly_one": True,
        },
        "authority": {
            "signed_maintenance_authorization_required": True,
            "automatic_recovery": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
            "hardware_backed_monotonic_counter_claimed": False,
        },
    }
    package["intent"] = intent
    return _reindex(artifacts, package)


def publish_atomic(out_dir: Path, artifacts: dict[str, bytes]) -> None:
    out_dir = out_dir.resolve()
    if out_dir.exists():
        raise CalibrationProvisioningError(f"recovery provisioning output already exists: {out_dir}")
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.", dir=out_dir.parent))
    try:
        for name, content in artifacts.items():
            (staging / name).write_bytes(content)
        staging.rename(out_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a monotonic ForgeSense calibration recovery package that restores an approved profile "
            "using the next higher sequence"
        )
    )
    parser.add_argument("source_change_dir", type=Path)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--change-package-dir", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--campaign-manifest", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--source-change-policy",
        type=Path,
        default=Path("hardware/calibration/calibration_source_change_policy_v1.json"),
    )
    parser.add_argument("--device-state", type=Path, required=True)
    parser.add_argument(
        "--provisioning-policy",
        type=Path,
        default=Path("hardware/calibration/calibration_provisioning_policy_v1.json"),
    )
    parser.add_argument("--reason", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        artifacts = build_recovery_bundle(
            args.source_change_dir,
            bundle_dir=args.bundle,
            change_package_dir=args.change_package_dir,
            approval_path=args.approval,
            source_root=args.source_root,
            campaign_manifest=args.campaign_manifest,
            repo_root=args.repo_root,
            source_change_policy_path=args.source_change_policy,
            device_state_path=args.device_state,
            provisioning_policy_path=args.provisioning_policy,
            reason=args.reason,
        )
        publish_atomic(args.out_dir, artifacts)
        package = json.loads(artifacts["provisioning.json"].decode("utf-8"))
        print(
            "calibration recovery package prepared: "
            f"device={package['device_id']} installed={package['sequence']['installed']} "
            f"candidate={package['sequence']['candidate']} automatic_recovery=false"
        )
        return 0
    except CalibrationProvisioningError as exc:
        print(f"calibration recovery preparation failed: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
