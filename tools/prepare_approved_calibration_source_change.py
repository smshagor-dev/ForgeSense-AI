from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile

try:
    from tools.prepare_calibration_change_package import (
        CalibrationChangePackageError,
        build_change_package,
    )
except ModuleNotFoundError:  # Direct execution from repository root.
    from prepare_calibration_change_package import CalibrationChangePackageError, build_change_package

APPROVAL_SCHEMA = "forgesense.calibration_approval.v1"
POLICY_SCHEMA = "forgesense.calibration_source_change_policy.v1"
SOURCE_PROFILE_SCHEMA = "forgesense.approved_calibration_source_profile.v1"
SOURCE_CHANGE_SCHEMA = "forgesense.calibration_source_change.v1"
ARTIFACT_INDEX_SCHEMA = "forgesense.calibration_source_change_artifact_index.v1"
HEX40 = re.compile(r"^[0-9a-fA-F]{40}$")
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
INT32_MIN = -(2**31)
INT32_MAX = 2**31 - 1
RAW24_MIN = -8388608
RAW24_MAX = 8388607


class CalibrationSourceChangeError(ValueError):
    pass


def _json_bytes(data: dict) -> bytes:
    return (json.dumps(data, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _canonical_sha256(data: dict) -> str:
    blob = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError as exc:
        raise CalibrationSourceChangeError(f"required file not found: {path}") from exc
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CalibrationSourceChangeError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CalibrationSourceChangeError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise CalibrationSourceChangeError(f"{label} must contain a JSON object: {path}")
    return value


def _finite(value: object, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise CalibrationSourceChangeError(f"{label} must be finite") from exc
    if not math.isfinite(result):
        raise CalibrationSourceChangeError(f"{label} must be finite")
    return result


def _require_hash(value: object, label: str) -> str:
    text = str(value or "")
    if not HEX64.fullmatch(text):
        raise CalibrationSourceChangeError(f"{label} must be a 64-hex SHA-256")
    return text.lower()


def _safe_rel_path(value: object, label: str) -> PurePosixPath:
    text = str(value or "").replace("\\", "/")
    path = PurePosixPath(text)
    if not text or path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise CalibrationSourceChangeError(f"{label} must be a safe relative path")
    return path


def _validate_policy(policy: dict) -> None:
    if policy.get("schema") != POLICY_SCHEMA:
        raise CalibrationSourceChangeError("unsupported calibration source-change policy schema")
    if not str(policy.get("policy_id", "")).strip():
        raise CalibrationSourceChangeError("source-change policy_id is required")
    current = policy.get("current")
    temperature = policy.get("temperature")
    accelerometer = policy.get("accelerometer")
    patch = policy.get("source_patch")
    if not all(isinstance(item, dict) for item in (current, temperature, accelerometer, patch)):
        raise CalibrationSourceChangeError("source-change policy sections are incomplete")
    maximum_denominator = int(current.get("maximum_gain_denominator", 0))
    if maximum_denominator < 1 or maximum_denominator > INT32_MAX:
        raise CalibrationSourceChangeError("current.maximum_gain_denominator is invalid")
    if _finite(current.get("maximum_abs_quantization_error_ma"), "current.maximum_abs_quantization_error_ma") < 0:
        raise CalibrationSourceChangeError("current quantization error limit must be non-negative")
    if _finite(temperature.get("maximum_abs_quantization_error_c"), "temperature.maximum_abs_quantization_error_c") < 0:
        raise CalibrationSourceChangeError("temperature quantization error limit must be non-negative")
    if accelerometer.get("runtime_mapping_supported") is not False:
        raise CalibrationSourceChangeError("policy must not claim accelerometer runtime mapping support")
    if accelerometer.get("required_disposition") != "deferred":
        raise CalibrationSourceChangeError("accelerometer required_disposition must be deferred")
    if patch.get("runtime_files_may_be_modified") is not False:
        raise CalibrationSourceChangeError("source-change policy must forbid runtime-file modification")
    if patch.get("existing_target_may_be_overwritten") is not False:
        raise CalibrationSourceChangeError("source-change policy must forbid profile overwrite")
    _safe_rel_path(patch.get("approved_profile_directory"), "source_patch.approved_profile_directory")
    baseline = policy.get("safety_baseline_files")
    if not isinstance(baseline, list) or not baseline:
        raise CalibrationSourceChangeError("safety_baseline_files must be a non-empty list")
    for index, path in enumerate(baseline):
        _safe_rel_path(path, f"safety_baseline_files[{index}]")


def _validate_approval(approval: dict, package: dict, package_sha256: str) -> None:
    if approval.get("schema") != APPROVAL_SCHEMA:
        raise CalibrationSourceChangeError("unsupported calibration approval schema")
    approval_id = str(approval.get("approval_id", "")).strip()
    if not SAFE_ID.fullmatch(approval_id):
        raise CalibrationSourceChangeError("approval_id must use safe identifier characters")
    if approval.get("decision") != "approved_for_source_change":
        raise CalibrationSourceChangeError("approval decision must be approved_for_source_change")
    if approval.get("campaign_id") != package.get("campaign_id"):
        raise CalibrationSourceChangeError("approval campaign_id does not match change package")
    commit = str(approval.get("repository_commit", "")).lower()
    if not HEX40.fullmatch(commit) or commit != str(package.get("repository_commit", "")).lower():
        raise CalibrationSourceChangeError("approval repository_commit does not match change package")
    if _require_hash(approval.get("evidence_root_sha256"), "approval.evidence_root_sha256") != _require_hash(
        package.get("evidence_root_sha256"), "change_package.evidence_root_sha256"
    ):
        raise CalibrationSourceChangeError("approval evidence_root_sha256 does not match change package")
    if _require_hash(approval.get("change_package_sha256"), "approval.change_package_sha256") != package_sha256:
        raise CalibrationSourceChangeError("approval change_package_sha256 does not match retained change package")

    approved_channels = approval.get("approved_channels")
    deferred_channels = approval.get("deferred_channels")
    if approved_channels != ["current", "temperature"]:
        raise CalibrationSourceChangeError("approval must explicitly approve only current and temperature")
    if deferred_channels != ["accelerometer"]:
        raise CalibrationSourceChangeError("approval must explicitly defer accelerometer")

    reviewer = approval.get("reviewer")
    if not isinstance(reviewer, dict) or not str(reviewer.get("name", "")).strip() or not str(reviewer.get("role", "")).strip():
        raise CalibrationSourceChangeError("approval reviewer name and role are required")
    reviewed_at = str(approval.get("reviewed_at_utc", "")).strip()
    try:
        parsed = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CalibrationSourceChangeError("reviewed_at_utc must be valid ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise CalibrationSourceChangeError("reviewed_at_utc must include UTC timezone")
    if not str(approval.get("rationale", "")).strip():
        raise CalibrationSourceChangeError("approval rationale is required")

    authority = approval.get("authority_acknowledgements")
    expected = {
        "source_control_change_required": True,
        "runtime_write_approved": False,
        "automatic_runtime_application": False,
        "hard_safety_limit_change_approved": False,
    }
    if not isinstance(authority, dict) or any(authority.get(key) is not value for key, value in expected.items()):
        raise CalibrationSourceChangeError("approval authority acknowledgements are invalid")


def _trunc_div(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise CalibrationSourceChangeError("internal denominator must be positive")
    if numerator >= 0:
        return numerator // denominator
    return -((-numerator) // denominator)


def _quantize_current(candidate: dict, raw_points: list[int], policy: dict) -> dict:
    slope = _finite(candidate.get("mean_slope_ma_per_count_candidate"), "current.mean_slope_ma_per_count_candidate")
    intercept = _finite(candidate.get("mean_intercept_ma_candidate"), "current.mean_intercept_ma_candidate")
    if slope <= 0:
        raise CalibrationSourceChangeError("current calibration slope must be positive")
    maximum_denominator = int(policy["current"]["maximum_gain_denominator"])
    fraction = Fraction(slope).limit_denominator(maximum_denominator)
    numerator = int(fraction.numerator)
    denominator = int(fraction.denominator)
    output_offset = int(round(intercept))
    for label, value in (("gain_numerator", numerator), ("gain_denominator", denominator), ("output_offset", output_offset)):
        if value < INT32_MIN or value > INT32_MAX:
            raise CalibrationSourceChangeError(f"current {label} exceeds int32 range")

    rows = []
    for raw in sorted(set(raw_points)):
        if raw < RAW24_MIN or raw > RAW24_MAX:
            raise CalibrationSourceChangeError(f"current regression raw point {raw} exceeds signed 24-bit range")
        floating = slope * raw + intercept
        quantized = _trunc_div(raw * numerator, denominator) + output_offset
        rows.append({
            "adc_raw": raw,
            "floating_candidate_ma": floating,
            "integer_candidate_ma": quantized,
            "error_ma": quantized - floating,
        })
    if not rows:
        raise CalibrationSourceChangeError("no retained current raw points are available for quantization regression")
    max_abs_error = max(abs(row["error_ma"]) for row in rows)
    error_limit = float(policy["current"]["maximum_abs_quantization_error_ma"])
    minimum_output = int(policy["current"].get("minimum_output_ma", 0))
    maximum_output = int(policy["current"].get("maximum_output_ma", 32767))
    outputs_in_range = all(minimum_output <= row["integer_candidate_ma"] <= maximum_output for row in rows)
    nonnegative = all(row["integer_candidate_ma"] >= 0 for row in rows)
    require_nonnegative = bool(policy["current"].get("require_nonnegative_at_reference_points", True))
    regression_pass = max_abs_error <= error_limit and outputs_in_range and (nonnegative or not require_nonnegative)
    if not regression_pass:
        raise CalibrationSourceChangeError(
            "current integer quantization failed regression gate "
            f"(max_abs_error_ma={max_abs_error:.6f}, limit={error_limit:.6f}, outputs_in_range={outputs_in_range}, nonnegative={nonnegative})"
        )
    return {
        "linear_calibration": {
            "raw_zero": 0,
            "gain_numerator": numerator,
            "gain_denominator": denominator,
            "output_offset": output_offset,
            "output_unit": "milliampere",
        },
        "floating_candidate": {"slope_ma_per_count": slope, "intercept_ma": intercept},
        "regression_points": rows,
        "maximum_abs_quantization_error_ma": max_abs_error,
        "policy_limit_ma": error_limit,
        "outputs_in_range": outputs_in_range,
        "nonnegative_at_reference_points": nonnegative,
        "regression_pass": True,
    }


def _quantize_temperature(candidate: dict, policy: dict) -> dict:
    offset_c = _finite(candidate.get("mean_offset_c_candidate"), "temperature.mean_offset_c_candidate")
    offset_deci_c = int(round(offset_c * 10.0))
    if offset_deci_c < INT32_MIN or offset_deci_c > INT32_MAX:
        raise CalibrationSourceChangeError("temperature offset exceeds int32 range")
    quantized_c = offset_deci_c / 10.0
    error_c = quantized_c - offset_c
    limit = float(policy["temperature"]["maximum_abs_quantization_error_c"])
    minimum_output = int(policy["temperature"].get("minimum_output_deci_c", -32768))
    maximum_output = int(policy["temperature"].get("maximum_output_deci_c", 32767))
    output_offset_in_range = minimum_output <= offset_deci_c <= maximum_output
    if abs(error_c) > limit or not output_offset_in_range:
        raise CalibrationSourceChangeError(
            "temperature offset quantization failed regression gate "
            f"(abs_error_c={abs(error_c):.6f}, limit={limit:.6f}, output_offset_in_range={output_offset_in_range})"
        )
    return {
        "linear_calibration": {
            "raw_zero": 0,
            "gain_numerator": 1,
            "gain_denominator": 1,
            "output_offset": offset_deci_c,
            "input_unit": "deci_degree_celsius",
            "output_unit": "deci_degree_celsius",
        },
        "floating_candidate_offset_c": offset_c,
        "quantized_offset_c": quantized_c,
        "quantization_error_c": error_c,
        "policy_limit_c": limit,
        "regression_pass": True,
    }


def _collect_current_raw_points(bundle_dir: Path) -> list[int]:
    campaign = _load_json(bundle_dir / "campaign.json", "campaign artifact")
    runs = campaign.get("runs")
    if not isinstance(runs, list) or not runs:
        raise CalibrationSourceChangeError("campaign artifact has no runs")
    values: list[int] = []
    for index, run in enumerate(runs):
        if not isinstance(run, dict):
            raise CalibrationSourceChangeError(f"campaign.runs[{index}] must be an object")
        relative = _safe_rel_path(run.get("capture_artifact"), f"campaign.runs[{index}].capture_artifact")
        capture = _load_json(bundle_dir.joinpath(*relative.parts), f"capture for campaign run {index}")
        current = capture.get("current")
        points = current.get("points") if isinstance(current, dict) else None
        if not isinstance(points, list) or not points:
            raise CalibrationSourceChangeError(f"capture for campaign run {index} has no current points")
        for point_index, point in enumerate(points):
            if not isinstance(point, dict):
                raise CalibrationSourceChangeError(f"current point {point_index} in campaign run {index} is invalid")
            raw = _finite(point.get("adc_raw"), f"campaign run {index} current point {point_index}.adc_raw")
            values.append(int(round(raw)))
    return values


def _safety_baseline(repo_root: Path, policy: dict) -> dict:
    repo_root = repo_root.resolve()
    entries = []
    seen: set[str] = set()
    for index, raw_path in enumerate(policy["safety_baseline_files"]):
        relative = _safe_rel_path(raw_path, f"safety_baseline_files[{index}]")
        text = str(relative)
        if text in seen:
            raise CalibrationSourceChangeError(f"duplicate safety baseline path: {text}")
        seen.add(text)
        path = repo_root.joinpath(*relative.parts)
        resolved = path.resolve()
        try:
            resolved.relative_to(repo_root)
        except ValueError as exc:
            raise CalibrationSourceChangeError(f"safety baseline path escapes repository root: {relative}") from exc
        entries.append({"path": text, "sha256": _file_sha256(resolved)})
    return {
        "schema": "forgesense.calibration_safety_baseline.v1",
        "policy_id": policy["policy_id"],
        "hard_safety_limit_change_approved": False,
        "files": entries,
    }


def _profile_path(campaign_id: str, policy: dict) -> str:
    if not SAFE_ID.fullmatch(campaign_id):
        raise CalibrationSourceChangeError("campaign_id cannot be used as an approved profile filename")
    directory = _safe_rel_path(policy["source_patch"]["approved_profile_directory"], "approved_profile_directory")
    return str(directory / f"{campaign_id}.json")


def _profile_patch(target: str, profile_bytes: bytes) -> bytes:
    text = profile_bytes.decode("utf-8")
    lines = text.splitlines()
    out = [
        f"diff --git a/{target} b/{target}",
        "new file mode 100644",
        "--- /dev/null",
        f"+++ b/{target}",
        f"@@ -0,0 +1,{len(lines)} @@",
    ]
    out.extend(f"+{line}" for line in lines)
    return ("\n".join(out) + "\n").encode("utf-8")


def build_source_change_bundle(
    bundle_dir: Path,
    *,
    change_package_dir: Path,
    approval_path: Path,
    source_root: Path,
    campaign_manifest: Path,
    repo_root: Path,
    policy_path: Path,
) -> dict[str, bytes]:
    bundle_dir = bundle_dir.resolve()
    change_package_dir = change_package_dir.resolve()
    repo_root = repo_root.resolve()

    try:
        expected_package, expected_signing = build_change_package(
            bundle_dir,
            source_root=source_root,
            campaign_manifest=campaign_manifest,
        )
    except CalibrationChangePackageError as exc:
        raise CalibrationSourceChangeError(f"reviewer package verification failed: {exc}") from exc

    retained_package = _load_json(change_package_dir / "change-package.json", "retained change package")
    retained_signing = _load_json(change_package_dir / "signing-request.json", "retained signing request")
    if retained_package != expected_package:
        raise CalibrationSourceChangeError("retained change package differs from verified campaign-derived package")
    if retained_signing != expected_signing:
        raise CalibrationSourceChangeError("retained signing request differs from verified campaign-derived request")

    retained_package_bytes = (change_package_dir / "change-package.json").read_bytes()
    package_sha256 = _sha256_bytes(retained_package_bytes)
    if package_sha256 != _require_hash(retained_signing.get("change_package_sha256"), "signing_request.change_package_sha256"):
        raise CalibrationSourceChangeError("retained change-package file hash does not match signing request")
    payload_text = (change_package_dir / "signing-payload.txt").read_text(encoding="utf-8")
    if payload_text != retained_signing.get("signing_payload"):
        raise CalibrationSourceChangeError("retained signing payload text differs from signing request")
    if _sha256_bytes(payload_text.encode("utf-8")) != _require_hash(retained_signing.get("payload_sha256"), "signing_request.payload_sha256"):
        raise CalibrationSourceChangeError("retained signing payload hash is invalid")

    approval = _load_json(approval_path, "calibration approval")
    policy = _load_json(policy_path, "calibration source-change policy")
    _validate_policy(policy)
    _validate_approval(approval, retained_package, package_sha256)

    candidates = retained_package.get("candidates")
    if not isinstance(candidates, dict):
        raise CalibrationSourceChangeError("change package candidates are missing")
    current = candidates.get("current")
    temperature = candidates.get("temperature")
    accelerometer = candidates.get("accelerometer")
    if not all(isinstance(item, dict) for item in (current, temperature, accelerometer)):
        raise CalibrationSourceChangeError("change package candidate sections are incomplete")

    raw_points = _collect_current_raw_points(bundle_dir)
    current_quantized = _quantize_current(current, raw_points, policy)
    temperature_quantized = _quantize_temperature(temperature, policy)
    accel_bias = accelerometer.get("mean_bias_mg_candidate")
    if not isinstance(accel_bias, dict):
        raise CalibrationSourceChangeError("accelerometer candidate bias mapping is missing")
    deferred_accel = {
        "status": "deferred",
        "runtime_mapping_supported": False,
        "reviewed_bias_mg_candidate": {
            axis: _finite(accel_bias.get(axis), f"accelerometer.mean_bias_mg_candidate.{axis}")
            for axis in ("x", "y", "z")
        },
        "note": "No accelerometer correction is emitted because CalibrationRecord v1 has no accelerometer calibration field.",
    }

    baseline = _safety_baseline(repo_root, policy)
    target = _profile_path(str(retained_package["campaign_id"]), policy)
    target_path = repo_root.joinpath(*PurePosixPath(target).parts)
    if target_path.exists():
        raise CalibrationSourceChangeError(f"approved source profile target already exists and will not be overwritten: {target}")

    profile = {
        "schema": SOURCE_PROFILE_SCHEMA,
        "approval_id": approval["approval_id"],
        "campaign_id": retained_package["campaign_id"],
        "repository_commit": retained_package["repository_commit"],
        "evidence_root_sha256": retained_package["evidence_root_sha256"],
        "change_package_sha256": package_sha256,
        "calibration_record_v1_candidate": {
            "temperature": temperature_quantized["linear_calibration"],
            "current": current_quantized["linear_calibration"],
        },
        "accelerometer": deferred_accel,
        "quantization_regression": {
            "current": current_quantized,
            "temperature": temperature_quantized,
        },
        "authority": {
            "source_review_artifact_only": True,
            "runtime_write_permitted": False,
            "automatic_runtime_application": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
    }
    profile_bytes = _json_bytes(profile)
    patch_bytes = _profile_patch(target, profile_bytes)
    baseline_bytes = _json_bytes(baseline)

    source_change = {
        "schema": SOURCE_CHANGE_SCHEMA,
        "approval_id": approval["approval_id"],
        "campaign_id": retained_package["campaign_id"],
        "repository_commit": retained_package["repository_commit"],
        "evidence_root_sha256": retained_package["evidence_root_sha256"],
        "change_package_sha256": package_sha256,
        "approval_sha256": _file_sha256(approval_path),
        "policy_id": policy["policy_id"],
        "policy_sha256": _file_sha256(policy_path),
        "patch_target": target,
        "approved_profile_sha256": _sha256_bytes(profile_bytes),
        "source_patch_sha256": _sha256_bytes(patch_bytes),
        "safety_baseline_sha256": _sha256_bytes(baseline_bytes),
        "approved_channels": ["current", "temperature"],
        "deferred_channels": ["accelerometer"],
        "quantization_regression_pass": True,
        "hard_safety_limits_changed": False,
        "runtime_files_changed": False,
        "authority": {
            "reviewer_approval_verified": True,
            "source_control_change_required": True,
            "runtime_write_permitted": False,
            "automatic_runtime_application": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
        "status": "approved source-change proposal; patch adds a reviewed profile only and does not provision runtime calibration",
    }
    source_change_bytes = _json_bytes(source_change)

    artifacts = {
        "source-change.json": source_change_bytes,
        "approved-profile.json": profile_bytes,
        "source-change.patch": patch_bytes,
        "safety-baseline.json": baseline_bytes,
    }
    index_core = {
        "schema": ARTIFACT_INDEX_SCHEMA,
        "campaign_id": retained_package["campaign_id"],
        "repository_commit": retained_package["repository_commit"],
        "artifacts": [
            {"path": path, "sha256": _sha256_bytes(content)}
            for path, content in sorted(artifacts.items())
        ],
        "authority": {
            "integrity_index_only": True,
            "runtime_write_permitted": False,
            "may_relax_hard_safety_limits": False,
        },
    }
    artifact_index = dict(index_core)
    artifact_index["root_sha256"] = _canonical_sha256(index_core)
    artifacts["artifact-index.json"] = _json_bytes(artifact_index)
    return artifacts


def publish_source_change(
    bundle_dir: Path,
    *,
    change_package_dir: Path,
    approval_path: Path,
    source_root: Path,
    campaign_manifest: Path,
    repo_root: Path,
    policy_path: Path,
    out_dir: Path,
) -> None:
    out_dir = out_dir.resolve()
    if out_dir.exists():
        raise CalibrationSourceChangeError(f"output directory already exists: {out_dir}")
    artifacts = build_source_change_bundle(
        bundle_dir,
        change_package_dir=change_package_dir,
        approval_path=approval_path,
        source_root=source_root,
        campaign_manifest=campaign_manifest,
        repo_root=repo_root,
        policy_path=policy_path,
    )
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.staging-", dir=out_dir.parent))
    try:
        for relative, content in artifacts.items():
            (staging / relative).write_bytes(content)
        staging.rename(out_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare an approved, source-controlled ForgeSense calibration profile patch without runtime provisioning"
    )
    parser.add_argument("bundle", type=Path)
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
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        publish_source_change(
            args.bundle,
            change_package_dir=args.change_package_dir,
            approval_path=args.approval,
            source_root=args.source_root,
            campaign_manifest=args.campaign_manifest,
            repo_root=args.repo_root,
            policy_path=args.policy,
            out_dir=args.out_dir,
        )
    except CalibrationSourceChangeError as exc:
        raise SystemExit(f"approved calibration source change failed: {exc}") from exc
    print(f"approved calibration source-change package written: {args.out_dir}; runtime_write_permitted=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
