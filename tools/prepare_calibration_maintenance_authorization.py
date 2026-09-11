from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

try:
    from commissioning.forgesense_commission.provisioning import (
        MaintenanceProvisioningError,
        load_provisioning_bundle,
    )
    from commissioning.forgesense_commission.recovery import RECOVERY_INTENT_SCHEMA
    from commissioning.forgesense_commission.signed_provisioning import (
        AUTHORIZATION_REQUEST_SCHEMA,
        authorization_payload,
    )
except ModuleNotFoundError:
    from forgesense_commission.provisioning import (  # type: ignore
        MaintenanceProvisioningError,
        load_provisioning_bundle,
    )
    from forgesense_commission.recovery import RECOVERY_INTENT_SCHEMA  # type: ignore
    from forgesense_commission.signed_provisioning import (  # type: ignore
        AUTHORIZATION_REQUEST_SCHEMA,
        authorization_payload,
    )

try:
    from tools.validate_signed_provisioning_policy import (
        SignedProvisioningPolicyError,
        validate_signed_provisioning_policy,
    )
    from tools.verify_calibration_provisioning import (
        CalibrationProvisioningVerificationError,
        verify_provisioning_bundle,
    )
    from tools.verify_calibration_recovery import (
        CalibrationRecoveryVerificationError,
        verify_recovery_bundle,
    )
except ModuleNotFoundError:
    from validate_signed_provisioning_policy import (  # type: ignore
        SignedProvisioningPolicyError,
        validate_signed_provisioning_policy,
    )
    from verify_calibration_provisioning import (  # type: ignore
        CalibrationProvisioningVerificationError,
        verify_provisioning_bundle,
    )
    from verify_calibration_recovery import (  # type: ignore
        CalibrationRecoveryVerificationError,
        verify_recovery_bundle,
    )


def _json_bytes(data: dict) -> bytes:
    return (json.dumps(data, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _recovery_verification_if_present(args: argparse.Namespace, package: dict) -> dict | None:
    intent = package.get("intent")
    if intent is None:
        return None
    if not isinstance(intent, dict) or intent.get("schema") != RECOVERY_INTENT_SCHEMA:
        raise MaintenanceProvisioningError("unsupported provisioning intent in authorization request")
    return verify_recovery_bundle(
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


def build_request(args: argparse.Namespace) -> dict[str, bytes]:
    # Signing requests are allowed only under the stricter physical-write policy,
    # not merely any package policy accepted by the offline bundle builder.
    validate_signed_provisioning_policy(args.provisioning_policy)

    verification = verify_provisioning_bundle(
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
    required_true = (
        "record_rederived",
        "source_derivation_reverified",
        "anti_rollback_gate_pass",
        "hard_safety_non_regression_pass",
    )
    for key in required_true:
        if verification.get(key) is not True:
            raise MaintenanceProvisioningError(
                f"provisioning verification did not establish required gate: {key}"
            )

    package, index, record_blob = load_provisioning_bundle(args.provisioning_dir)
    recovery_verification = _recovery_verification_if_present(args, package)
    sequence = package.get("sequence")
    if not isinstance(sequence, dict):
        raise MaintenanceProvisioningError("provisioning sequence metadata is missing")
    expected_installed = int(sequence.get("installed", -1))
    candidate_sequence = int(sequence.get("candidate", -1))
    artifact_root = str(index.get("root_sha256", ""))
    device_id = str(package.get("device_id", ""))

    payload = authorization_payload(
        device_id=device_id,
        expected_installed_sequence=expected_installed,
        artifact_root_sha256=artifact_root,
        record_blob=record_blob,
    )
    request = {
        "schema": AUTHORIZATION_REQUEST_SCHEMA,
        "signature_format": "ECDSA-P256-SHA256-DER",
        "device_id": device_id,
        "expected_installed_sequence": expected_installed,
        "candidate_sequence": candidate_sequence,
        "artifact_root_sha256": artifact_root,
        "record_sha256": _sha256_bytes(record_blob),
        "payload_sha256": _sha256_bytes(payload),
        "provisioning_verification": {
            key: verification.get(key) is True for key in required_true
        },
        "recovery_verification": (
            {
                "schema": recovery_verification.get("schema"),
                "active_record_sha256_bound": recovery_verification.get("active_record_sha256_bound") is True,
                "approved_profile_reverified": recovery_verification.get("approved_profile_reverified") is True,
                "monotonic_sequence_preserved": recovery_verification.get("monotonic_sequence_preserved") is True,
                "sequence_decrement_performed": False,
            }
            if recovery_verification is not None
            else None
        ),
        "authority": {
            "request_generation_only": True,
            "external_signature_required": True,
            "private_key_accessed_by_tool": False,
            "automatic_provisioning": False,
            "automatic_recovery": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
        "signing_instruction": (
            "Sign authorization-payload.bin externally with the approved NIST P-256 private key using ECDSA/SHA-256. "
            "Provide the DER-encoded ECDSA signature to package_calibration_maintenance_authorization.py."
        ),
    }
    return {
        "authorization-request.json": _json_bytes(request),
        "authorization-payload.bin": payload,
        "authorization-payload.sha256": (_sha256_bytes(payload) + "\n").encode("ascii"),
    }


def publish_atomic(out_dir: Path, artifacts: dict[str, bytes]) -> None:
    out_dir = out_dir.resolve()
    if out_dir.exists():
        raise MaintenanceProvisioningError(f"authorization request output already exists: {out_dir}")
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
        description="Prepare an externally signed ForgeSense calibration maintenance authorization request"
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
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        publish_atomic(args.out_dir, build_request(args))
        return 0
    except (
        MaintenanceProvisioningError,
        CalibrationProvisioningVerificationError,
        CalibrationRecoveryVerificationError,
        SignedProvisioningPolicyError,
    ) as exc:
        print(f"maintenance authorization request failed: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
