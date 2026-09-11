from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

try:
    from commissioning.forgesense_commission.provisioning import (
        MaintenanceProvisioningError,
        load_provisioning_bundle,
    )
except ModuleNotFoundError:
    from forgesense_commission.provisioning import MaintenanceProvisioningError, load_provisioning_bundle  # type: ignore

try:
    from tools.prepare_calibration_provisioning import _file_sha256, _load_json
    from tools.prepare_calibration_recovery import RECOVERY_INTENT_SCHEMA
    from tools.verify_calibration_provisioning import (
        CalibrationProvisioningVerificationError,
        verify_provisioning_bundle,
    )
except ModuleNotFoundError:
    from prepare_calibration_provisioning import _file_sha256, _load_json  # type: ignore
    from prepare_calibration_recovery import RECOVERY_INTENT_SCHEMA  # type: ignore
    from verify_calibration_provisioning import (  # type: ignore
        CalibrationProvisioningVerificationError,
        verify_provisioning_bundle,
    )

VERIFICATION_SCHEMA = "forgesense.calibration_recovery_verification.v1"
CALIBRATION_RECORD_SIZE = 48


class CalibrationRecoveryVerificationError(ValueError):
    pass


def _decode_active_record(state: dict) -> bytes:
    text = state.get("active_record_hex")
    if not isinstance(text, str) or len(text) != CALIBRATION_RECORD_SIZE * 2:
        raise CalibrationRecoveryVerificationError("device state lacks the exact active CalibrationRecord readback")
    try:
        blob = bytes.fromhex(text)
    except ValueError as exc:
        raise CalibrationRecoveryVerificationError("device-state active record hex is invalid") from exc
    if len(blob) != CALIBRATION_RECORD_SIZE:
        raise CalibrationRecoveryVerificationError("device-state active record is not 48 bytes")
    if hashlib.sha256(blob).hexdigest() != state.get("active_record_sha256"):
        raise CalibrationRecoveryVerificationError("device-state active record SHA-256 mismatch")
    sequence = struct.unpack_from("<I", blob, 8)[0]
    crc = struct.unpack_from("<I", blob, 44)[0]
    if sequence != int(state.get("installed_sequence", -1)):
        raise CalibrationRecoveryVerificationError("active record sequence differs from installed device sequence")
    if crc != int(state.get("installed_record_crc32", -1)):
        raise CalibrationRecoveryVerificationError("active record CRC differs from installed device CRC")
    return blob


def verify_recovery_bundle(
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
    generic = verify_provisioning_bundle(
        provisioning_dir,
        source_change_dir=source_change_dir,
        bundle_dir=bundle_dir,
        change_package_dir=change_package_dir,
        approval_path=approval_path,
        source_root=source_root,
        campaign_manifest=campaign_manifest,
        repo_root=repo_root,
        source_change_policy_path=source_change_policy_path,
        device_state_path=device_state_path,
        provisioning_policy_path=provisioning_policy_path,
    )
    package, _, candidate_blob = load_provisioning_bundle(provisioning_dir)
    state = _load_json(device_state_path, "calibration device state")
    active_blob = _decode_active_record(state)

    intent = package.get("intent")
    if not isinstance(intent, dict) or intent.get("schema") != RECOVERY_INTENT_SCHEMA:
        raise CalibrationRecoveryVerificationError("calibration recovery intent is missing or unsupported")
    if intent.get("mode") != "restore_approved_profile_with_new_sequence":
        raise CalibrationRecoveryVerificationError("calibration recovery mode is unsupported")
    reason = str(intent.get("reason", "")).strip()
    if len(reason) < 12:
        raise CalibrationRecoveryVerificationError("calibration recovery reason is too short")

    source = intent.get("from_active_record")
    target = intent.get("to_approved_profile")
    sequence_semantics = intent.get("sequence_semantics")
    authority = intent.get("authority")
    if not all(isinstance(value, dict) for value in (source, target, sequence_semantics, authority)):
        raise CalibrationRecoveryVerificationError("calibration recovery intent sections are incomplete")

    active_sequence = struct.unpack_from("<I", active_blob, 8)[0]
    active_crc = struct.unpack_from("<I", active_blob, 44)[0]
    active_sha = hashlib.sha256(active_blob).hexdigest()
    if source.get("sha256") != active_sha or int(source.get("sequence", -1)) != active_sequence:
        raise CalibrationRecoveryVerificationError("recovery source active-record binding is invalid")
    if int(source.get("crc32_ieee", -1)) != active_crc:
        raise CalibrationRecoveryVerificationError("recovery source active-record CRC binding is invalid")

    package_sequence = package.get("sequence")
    if not isinstance(package_sequence, dict):
        raise CalibrationRecoveryVerificationError("recovery package sequence metadata is missing")
    installed = int(package_sequence.get("installed", -1))
    candidate = int(package_sequence.get("candidate", -1))
    if installed != active_sequence or candidate != installed + 1:
        raise CalibrationRecoveryVerificationError("recovery candidate must use exactly the next higher sequence")
    if (
        int(sequence_semantics.get("installed", -1)) != installed
        or int(sequence_semantics.get("candidate", -1)) != candidate
        or sequence_semantics.get("candidate_is_new_higher_sequence") is not True
        or sequence_semantics.get("decrement_permitted") is not False
        or sequence_semantics.get("increment_exactly_one") is not True
    ):
        raise CalibrationRecoveryVerificationError("recovery sequence semantics are invalid")

    if candidate_blob[12:44] == active_blob[12:44]:
        raise CalibrationRecoveryVerificationError("recovery target coefficients equal the active coefficients")

    profile_path = source_change_dir.resolve() / "approved-profile.json"
    profile = _load_json(profile_path, "approved calibration profile")
    if target.get("campaign_id") != package.get("campaign_id") or target.get("campaign_id") != profile.get("campaign_id"):
        raise CalibrationRecoveryVerificationError("recovery target campaign binding is invalid")
    if target.get("approval_id") != package.get("approval_id") or target.get("approval_id") != profile.get("approval_id"):
        raise CalibrationRecoveryVerificationError("recovery target approval binding is invalid")
    if target.get("approved_profile_sha256") != _file_sha256(profile_path):
        raise CalibrationRecoveryVerificationError("recovery target approved-profile SHA-256 is invalid")
    if target.get("candidate_record_sha256") != hashlib.sha256(candidate_blob).hexdigest():
        raise CalibrationRecoveryVerificationError("recovery target candidate-record SHA-256 is invalid")

    expected_authority = {
        "signed_maintenance_authorization_required": True,
        "automatic_recovery": False,
        "may_control_actuators": False,
        "may_relax_hard_safety_limits": False,
        "hardware_backed_monotonic_counter_claimed": False,
    }
    for key, expected in expected_authority.items():
        if authority.get(key) is not expected:
            raise CalibrationRecoveryVerificationError(f"recovery authority field {key} is invalid")

    if generic.get("record_rederived") is not True or generic.get("source_derivation_reverified") is not True:
        raise CalibrationRecoveryVerificationError("generic provisioning verification did not rederive recovery record")

    return {
        "schema": VERIFICATION_SCHEMA,
        "device_id": package["device_id"],
        "campaign_id": package["campaign_id"],
        "approval_id": package["approval_id"],
        "from_sequence": installed,
        "to_sequence": candidate,
        "active_record_sha256_bound": True,
        "approved_profile_reverified": True,
        "record_rederived": True,
        "coefficients_changed": True,
        "monotonic_sequence_preserved": True,
        "sequence_decrement_performed": False,
        "signed_maintenance_authorization_required": True,
        "hard_safety_non_regression_pass": generic.get("hard_safety_non_regression_pass") is True,
        "authority": {
            "verification_only": True,
            "automatic_recovery": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
            "hardware_backed_monotonic_counter_claimed": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify a ForgeSense monotonic calibration recovery package without writing a device"
    )
    parser.add_argument("provisioning_dir", type=Path)
    parser.add_argument("--source-change-dir", type=Path, required=True)
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
    parser.add_argument("--report-out", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = verify_recovery_bundle(
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
    except (CalibrationRecoveryVerificationError, CalibrationProvisioningVerificationError, MaintenanceProvisioningError) as exc:
        print(f"calibration recovery verification failed: {exc}")
        return 2
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(
        "calibration recovery verification PASS: "
        f"from={result['from_sequence']} to={result['to_sequence']} decrement=false automatic_recovery=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
