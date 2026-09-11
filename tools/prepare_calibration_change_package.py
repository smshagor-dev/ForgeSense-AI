from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile

try:
    from tools.verify_calibration_bundle import (
        CalibrationBundleVerificationError,
        verify_bundle,
    )
except ModuleNotFoundError:  # Direct execution from repository root.
    from verify_calibration_bundle import CalibrationBundleVerificationError, verify_bundle

CHANGE_PACKAGE_SCHEMA = "forgesense.calibration_change_package.v1"
SIGNING_REQUEST_SCHEMA = "forgesense.calibration_signing_request.v1"
SIGNING_DOMAIN = "ForgeSense-Calibration-Change-Package-v1"


class CalibrationChangePackageError(ValueError):
    pass


def _json_bytes(data: dict) -> bytes:
    return (json.dumps(data, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path, label: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CalibrationChangePackageError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CalibrationChangePackageError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise CalibrationChangePackageError(f"{label} must contain a JSON object: {path}")
    return data


def _finite(value: object, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise CalibrationChangePackageError(f"{label} must be finite") from exc
    if not math.isfinite(result):
        raise CalibrationChangePackageError(f"{label} must be finite")
    return result


def _candidate_summary(review: dict) -> dict:
    current = review.get("current")
    temperature = review.get("temperature")
    accelerometer = review.get("accelerometer")
    if not isinstance(current, dict) or not isinstance(temperature, dict) or not isinstance(accelerometer, dict):
        raise CalibrationChangePackageError("review is missing calibration candidate sections")

    bias = accelerometer.get("mean_bias_mg_candidate")
    if not isinstance(bias, dict):
        raise CalibrationChangePackageError("review accelerometer mean_bias_mg_candidate is missing")
    normalized_bias = {
        axis: _finite(bias.get(axis), f"review.accelerometer.mean_bias_mg_candidate.{axis}")
        for axis in ("x", "y", "z")
    }

    return {
        "current": {
            "mean_slope_ma_per_count_candidate": _finite(
                current.get("mean_slope_ma_per_count_candidate"),
                "review.current.mean_slope_ma_per_count_candidate",
            ),
            "mean_intercept_ma_candidate": _finite(
                current.get("mean_intercept_ma_candidate"),
                "review.current.mean_intercept_ma_candidate",
            ),
            "engineering_uncertainty_proxy_ma_k2": _finite(
                current.get("engineering_uncertainty_proxy_ma_k2"),
                "review.current.engineering_uncertainty_proxy_ma_k2",
            ),
            "repeatability_pass": current.get("repeatability_pass") is True,
        },
        "temperature": {
            "mean_offset_c_candidate": _finite(
                temperature.get("mean_offset_c_candidate"),
                "review.temperature.mean_offset_c_candidate",
            ),
            "engineering_uncertainty_proxy_c_k2": _finite(
                temperature.get("engineering_uncertainty_proxy_c_k2"),
                "review.temperature.engineering_uncertainty_proxy_c_k2",
            ),
            "repeatability_pass": temperature.get("repeatability_pass") is True,
        },
        "accelerometer": {
            "mean_bias_mg_candidate": normalized_bias,
            "engineering_uncertainty_proxy_mg_k2": _finite(
                accelerometer.get("engineering_uncertainty_proxy_mg_k2"),
                "review.accelerometer.engineering_uncertainty_proxy_mg_k2",
            ),
            "repeatability_pass": accelerometer.get("repeatability_pass") is True,
        },
    }


def build_change_package(
    bundle_dir: Path,
    *,
    source_root: Path,
    campaign_manifest: Path,
) -> tuple[dict, dict]:
    try:
        verification = verify_bundle(
            bundle_dir,
            source_root=source_root,
            campaign_manifest=campaign_manifest,
        )
    except CalibrationBundleVerificationError as exc:
        raise CalibrationChangePackageError(f"bundle verification failed: {exc}") from exc

    if verification.get("bundle_integrity_pass") is not True:
        raise CalibrationChangePackageError("bundle integrity verification did not pass")
    if verification.get("source_provenance_pass") is not True:
        raise CalibrationChangePackageError("source provenance verification is required")
    if verification.get("review_ready") is not True:
        raise CalibrationChangePackageError("campaign is not review-ready")

    bundle_dir = bundle_dir.resolve()
    campaign = _load_json(bundle_dir / "campaign.json", "campaign artifact")
    review = _load_json(bundle_dir / "review.json", "review artifact")
    evidence_index = _load_json(bundle_dir / "evidence-index.json", "evidence index")
    candidates = _candidate_summary(review)

    if not all(
        section.get("repeatability_pass") is True
        for section in candidates.values()
    ):
        raise CalibrationChangePackageError("review-ready campaign has a non-passing candidate section")

    package = {
        "schema": CHANGE_PACKAGE_SCHEMA,
        "campaign_id": verification["campaign_id"],
        "repository_commit": verification["repository_commit"],
        "evidence_root_sha256": verification["evidence_root_sha256"],
        "review_sha256": campaign["review_sha256"],
        "review_ready": True,
        "source_provenance_verified": True,
        "source_items_verified": verification["source_items_verified"],
        "candidates": candidates,
        "review_checks": review.get("checks", {}),
        "evidence": {
            "campaign_artifact": "campaign.json",
            "review_artifact": "review.json",
            "evidence_index_artifact": "evidence-index.json",
            "integrity_algorithm": evidence_index.get("integrity_seal", {}).get("algorithm"),
        },
        "authority": {
            "reviewer_approval_required": True,
            "source_control_change_required": True,
            "runtime_write_permitted": False,
            "automatic_runtime_application": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
        "status": "reviewer-ready evidence package; no calibration is applied by this artifact",
    }
    package_bytes = _json_bytes(package)
    package_sha256 = _sha256_bytes(package_bytes)
    signing_payload = (
        f"{SIGNING_DOMAIN}\n"
        f"campaign_id={package['campaign_id']}\n"
        f"repository_commit={package['repository_commit']}\n"
        f"evidence_root_sha256={package['evidence_root_sha256']}\n"
        f"review_sha256={package['review_sha256']}\n"
        f"change_package_sha256={package_sha256}\n"
    )
    signing_request = {
        "schema": SIGNING_REQUEST_SCHEMA,
        "campaign_id": package["campaign_id"],
        "repository_commit": package["repository_commit"],
        "signature_domain": SIGNING_DOMAIN,
        "payload_encoding": "utf-8",
        "signing_payload": signing_payload,
        "payload_sha256": _sha256_bytes(signing_payload.encode("utf-8")),
        "change_package_sha256": package_sha256,
        "external_signature_required": True,
        "digital_signature_present": False,
        "note": (
            "Sign the exact UTF-8 signing_payload with an independently managed signing system. "
            "This utility does not access private keys and does not claim a signature exists."
        ),
        "authority": {
            "signing_request_only": True,
            "automatic_runtime_application": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
    }
    return package, signing_request


def publish_change_package(
    bundle_dir: Path,
    *,
    source_root: Path,
    campaign_manifest: Path,
    out_dir: Path,
) -> None:
    out_dir = out_dir.resolve()
    if out_dir.exists():
        raise CalibrationChangePackageError(f"output directory already exists: {out_dir}")
    package, signing_request = build_change_package(
        bundle_dir,
        source_root=source_root,
        campaign_manifest=campaign_manifest,
    )
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.staging-", dir=out_dir.parent))
    try:
        (staging / "change-package.json").write_bytes(_json_bytes(package))
        (staging / "signing-request.json").write_bytes(_json_bytes(signing_request))
        (staging / "signing-payload.txt").write_text(signing_request["signing_payload"], encoding="utf-8")
        staging.rename(out_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a reviewer-ready ForgeSense calibration change package from verified campaign evidence"
    )
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--campaign-manifest", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        publish_change_package(
            args.bundle,
            source_root=args.source_root,
            campaign_manifest=args.campaign_manifest,
            out_dir=args.out_dir,
        )
    except CalibrationChangePackageError as exc:
        raise SystemExit(f"calibration change package failed: {exc}") from exc
    print(f"calibration change package written: {args.out_dir}; runtime_write_permitted=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
