from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from tools.prepare_calibration_change_package import (
        CalibrationChangePackageError,
        build_change_package,
    )
    from tools.prepare_approved_calibration_source_change import (
        CalibrationSourceChangeError,
        _collect_current_raw_points,
        _quantize_current,
        _quantize_temperature,
        _validate_approval,
        _validate_policy,
    )
    from tools.verify_calibration_source_change import (
        CalibrationSourceChangeVerificationError,
        verify_source_change,
    )
except ModuleNotFoundError:  # Direct execution from repository root.
    from prepare_calibration_change_package import CalibrationChangePackageError, build_change_package
    from prepare_approved_calibration_source_change import (
        CalibrationSourceChangeError,
        _collect_current_raw_points,
        _quantize_current,
        _quantize_temperature,
        _validate_approval,
        _validate_policy,
    )
    from verify_calibration_source_change import CalibrationSourceChangeVerificationError, verify_source_change

VERIFICATION_SCHEMA = "forgesense.calibration_source_derivation_verification.v1"


class CalibrationSourceDerivationError(ValueError):
    pass


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CalibrationSourceDerivationError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CalibrationSourceDerivationError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise CalibrationSourceDerivationError(f"{label} must contain a JSON object: {path}")
    return value


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_source_derivation(
    change_dir: Path,
    *,
    bundle_dir: Path,
    change_package_dir: Path,
    approval_path: Path,
    source_root: Path,
    campaign_manifest: Path,
    repo_root: Path,
    policy_path: Path,
) -> dict:
    try:
        structural = verify_source_change(
            change_dir,
            approval_path=approval_path,
            change_package_dir=change_package_dir,
            repo_root=repo_root,
            policy_path=policy_path,
        )
    except CalibrationSourceChangeVerificationError as exc:
        raise CalibrationSourceDerivationError(f"source-change structural verification failed: {exc}") from exc

    try:
        expected_package, expected_signing = build_change_package(
            bundle_dir,
            source_root=source_root,
            campaign_manifest=campaign_manifest,
        )
    except CalibrationChangePackageError as exc:
        raise CalibrationSourceDerivationError(f"reviewer package re-derivation failed: {exc}") from exc

    retained_package = _load_json(change_package_dir / "change-package.json", "retained change package")
    retained_signing = _load_json(change_package_dir / "signing-request.json", "retained signing request")
    if retained_package != expected_package:
        raise CalibrationSourceDerivationError("retained change package differs from campaign-derived package")
    if retained_signing != expected_signing:
        raise CalibrationSourceDerivationError("retained signing request differs from campaign-derived request")
    payload_text = (change_package_dir / "signing-payload.txt").read_text(encoding="utf-8")
    if payload_text != expected_signing.get("signing_payload"):
        raise CalibrationSourceDerivationError("retained signing payload differs from campaign-derived request")

    policy = _load_json(policy_path, "calibration source-change policy")
    approval = _load_json(approval_path, "calibration approval")
    package_sha = _sha256_bytes((change_package_dir / "change-package.json").read_bytes())
    try:
        _validate_policy(policy)
        _validate_approval(approval, retained_package, package_sha)
    except CalibrationSourceChangeError as exc:
        raise CalibrationSourceDerivationError(f"approval or source-change policy validation failed: {exc}") from exc

    candidates = retained_package.get("candidates")
    if not isinstance(candidates, dict):
        raise CalibrationSourceDerivationError("retained change package candidates are missing")
    current_candidate = candidates.get("current")
    temperature_candidate = candidates.get("temperature")
    accelerometer_candidate = candidates.get("accelerometer")
    if not all(isinstance(item, dict) for item in (current_candidate, temperature_candidate, accelerometer_candidate)):
        raise CalibrationSourceDerivationError("retained change package candidate sections are incomplete")

    try:
        raw_points = _collect_current_raw_points(bundle_dir.resolve())
        expected_current = _quantize_current(current_candidate, raw_points, policy)
        expected_temperature = _quantize_temperature(temperature_candidate, policy)
    except CalibrationSourceChangeError as exc:
        raise CalibrationSourceDerivationError(f"coefficient re-derivation failed: {exc}") from exc

    profile = _load_json(change_dir / "approved-profile.json", "approved calibration profile")
    record = profile.get("calibration_record_v1_candidate")
    regression = profile.get("quantization_regression")
    if not isinstance(record, dict) or not isinstance(regression, dict):
        raise CalibrationSourceDerivationError("approved profile is missing calibration record or regression data")
    if record.get("current") != expected_current["linear_calibration"]:
        raise CalibrationSourceDerivationError("approved current coefficients differ from evidence-derived integer coefficients")
    if record.get("temperature") != expected_temperature["linear_calibration"]:
        raise CalibrationSourceDerivationError("approved temperature coefficients differ from evidence-derived integer coefficients")
    if regression.get("current") != expected_current:
        raise CalibrationSourceDerivationError("approved current quantization regression differs from retained evidence")
    if regression.get("temperature") != expected_temperature:
        raise CalibrationSourceDerivationError("approved temperature quantization regression differs from retained evidence")

    expected_bias = accelerometer_candidate.get("mean_bias_mg_candidate")
    accelerometer = profile.get("accelerometer")
    if not isinstance(expected_bias, dict) or not isinstance(accelerometer, dict):
        raise CalibrationSourceDerivationError("accelerometer traceability data is missing")
    try:
        expected_bias_mapping = {axis: float(expected_bias[axis]) for axis in ("x", "y", "z")}
    except (KeyError, TypeError, ValueError) as exc:
        raise CalibrationSourceDerivationError("reviewer package accelerometer bias is incomplete") from exc
    recorded_bias = accelerometer.get("reviewed_bias_mg_candidate")
    if recorded_bias != expected_bias_mapping:
        raise CalibrationSourceDerivationError("deferred accelerometer bias differs from reviewer package")
    if accelerometer.get("status") != "deferred" or accelerometer.get("runtime_mapping_supported") is not False:
        raise CalibrationSourceDerivationError("accelerometer correction must remain deferred")

    source_change = _load_json(change_dir / "source-change.json", "source-change summary")
    if source_change.get("change_package_sha256") != package_sha:
        raise CalibrationSourceDerivationError("source-change summary is not bound to retained change-package bytes")
    if source_change.get("evidence_root_sha256") != retained_package.get("evidence_root_sha256"):
        raise CalibrationSourceDerivationError("source-change evidence root differs from reviewer package")
    if source_change.get("approval_id") != approval.get("approval_id"):
        raise CalibrationSourceDerivationError("source-change approval_id differs from validated approval")

    return {
        "schema": VERIFICATION_SCHEMA,
        "campaign_id": retained_package["campaign_id"],
        "repository_commit": retained_package["repository_commit"],
        "approval_id": source_change["approval_id"],
        "structural_verification_pass": structural.get("artifact_integrity_pass") is True,
        "reviewer_package_rederived": True,
        "approval_semantics_revalidated": True,
        "current_coefficients_rederived": True,
        "temperature_coefficients_rederived": True,
        "quantization_regression_rederived": True,
        "accelerometer_deferred_traceability_pass": True,
        "hard_safety_non_regression_pass": structural.get("hard_safety_non_regression_pass") is True,
        "runtime_source_unchanged": structural.get("runtime_source_unchanged") is True,
        "authority": {
            "verification_only": True,
            "runtime_write_permitted": False,
            "automatic_runtime_application": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Re-derive approved ForgeSense calibration source coefficients from verified campaign evidence"
    )
    parser.add_argument("change_dir", type=Path)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--change-package-dir", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--campaign-manifest", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("hardware/calibration/calibration_source_change_policy_v1.json"),
    )
    parser.add_argument("--report-out", type=Path)
    args = parser.parse_args()
    try:
        result = verify_source_derivation(
            args.change_dir,
            bundle_dir=args.bundle,
            change_package_dir=args.change_package_dir,
            approval_path=args.approval,
            source_root=args.source_root,
            campaign_manifest=args.campaign_manifest,
            repo_root=args.repo_root,
            policy_path=args.policy,
        )
    except CalibrationSourceDerivationError as exc:
        raise SystemExit(f"calibration source derivation verification failed: {exc}") from exc
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        "calibration source derivation verification PASS: "
        f"current={result['current_coefficients_rederived']} "
        f"temperature={result['temperature_coefficients_rederived']} "
        f"hard_safety_non_regression={result['hard_safety_non_regression_pass']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
