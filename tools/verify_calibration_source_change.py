from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

SOURCE_CHANGE_SCHEMA = "forgesense.calibration_source_change.v1"
SOURCE_PROFILE_SCHEMA = "forgesense.approved_calibration_source_profile.v1"
ARTIFACT_INDEX_SCHEMA = "forgesense.calibration_source_change_artifact_index.v1"
POLICY_SCHEMA = "forgesense.calibration_source_change_policy.v1"
APPROVAL_SCHEMA = "forgesense.calibration_approval.v1"
VERIFICATION_SCHEMA = "forgesense.calibration_source_change_verification.v1"
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
EXPECTED_ARTIFACTS = {
    "approved-profile.json",
    "safety-baseline.json",
    "source-change.json",
    "source-change.patch",
}


class CalibrationSourceChangeVerificationError(ValueError):
    pass


def _canonical_sha256(data: dict) -> str:
    blob = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError as exc:
        raise CalibrationSourceChangeVerificationError(f"required file not found: {path}") from exc
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CalibrationSourceChangeVerificationError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CalibrationSourceChangeVerificationError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise CalibrationSourceChangeVerificationError(f"{label} must contain a JSON object: {path}")
    return value


def _require_hash(value: object, label: str) -> str:
    text = str(value or "")
    if not HEX64.fullmatch(text):
        raise CalibrationSourceChangeVerificationError(f"{label} must be a 64-hex SHA-256")
    return text.lower()


def _safe_rel_path(value: object, label: str) -> PurePosixPath:
    text = str(value or "").replace("\\", "/")
    path = PurePosixPath(text)
    if not text or path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise CalibrationSourceChangeVerificationError(f"{label} must be a safe relative path")
    return path


def _strict_authority(mapping: object, expected: dict[str, bool], label: str) -> None:
    if not isinstance(mapping, dict):
        raise CalibrationSourceChangeVerificationError(f"{label} authority is missing")
    for key, expected_value in expected.items():
        if mapping.get(key) is not expected_value:
            raise CalibrationSourceChangeVerificationError(f"{label} authority field {key} is invalid")


def _confined(repo_root: Path, relative: PurePosixPath, label: str) -> Path:
    repo_root = repo_root.resolve()
    target = repo_root.joinpath(*relative.parts).resolve()
    try:
        target.relative_to(repo_root)
    except ValueError as exc:
        raise CalibrationSourceChangeVerificationError(f"{label} escapes repository root: {relative}") from exc
    return target


def verify_source_change(
    change_dir: Path,
    *,
    approval_path: Path,
    change_package_dir: Path,
    repo_root: Path,
    policy_path: Path,
) -> dict:
    change_dir = change_dir.resolve()
    repo_root = repo_root.resolve()
    index = _load_json(change_dir / "artifact-index.json", "source-change artifact index")
    if index.get("schema") != ARTIFACT_INDEX_SCHEMA:
        raise CalibrationSourceChangeVerificationError("unsupported source-change artifact index schema")
    _strict_authority(
        index.get("authority"),
        {
            "integrity_index_only": True,
            "runtime_write_permitted": False,
            "may_relax_hard_safety_limits": False,
        },
        "artifact index",
    )
    claimed_root = _require_hash(index.get("root_sha256"), "artifact_index.root_sha256")
    index_core = {key: value for key, value in index.items() if key != "root_sha256"}
    if _canonical_sha256(index_core) != claimed_root:
        raise CalibrationSourceChangeVerificationError("source-change artifact index root SHA-256 mismatch")

    artifacts = index.get("artifacts")
    if not isinstance(artifacts, list):
        raise CalibrationSourceChangeVerificationError("source-change artifact index has no artifacts")
    indexed: set[str] = set()
    for item_index, item in enumerate(artifacts):
        if not isinstance(item, dict):
            raise CalibrationSourceChangeVerificationError(f"artifact index entry {item_index} is invalid")
        relative = _safe_rel_path(item.get("path"), f"artifacts[{item_index}].path")
        text = str(relative)
        if text in indexed:
            raise CalibrationSourceChangeVerificationError(f"duplicate source-change artifact {text}")
        indexed.add(text)
        expected = _require_hash(item.get("sha256"), f"artifacts[{item_index}].sha256")
        if _file_sha256(change_dir.joinpath(*relative.parts)) != expected:
            raise CalibrationSourceChangeVerificationError(f"source-change artifact hash mismatch: {text}")
    if indexed != EXPECTED_ARTIFACTS:
        raise CalibrationSourceChangeVerificationError(
            f"source-change artifact set mismatch: expected {sorted(EXPECTED_ARTIFACTS)}, got {sorted(indexed)}"
        )
    actual_files = {
        path.relative_to(change_dir).as_posix()
        for path in change_dir.rglob("*")
        if path.is_file() and path.name != "artifact-index.json"
    }
    if actual_files != EXPECTED_ARTIFACTS:
        raise CalibrationSourceChangeVerificationError("source-change directory contains missing or unindexed files")

    source_change = _load_json(change_dir / "source-change.json", "source-change summary")
    profile = _load_json(change_dir / "approved-profile.json", "approved calibration profile")
    baseline = _load_json(change_dir / "safety-baseline.json", "safety baseline")
    approval = _load_json(approval_path, "calibration approval")
    package = _load_json(change_package_dir / "change-package.json", "retained change package")
    policy = _load_json(policy_path, "source-change policy")

    if source_change.get("schema") != SOURCE_CHANGE_SCHEMA:
        raise CalibrationSourceChangeVerificationError("unsupported source-change summary schema")
    if profile.get("schema") != SOURCE_PROFILE_SCHEMA:
        raise CalibrationSourceChangeVerificationError("unsupported approved profile schema")
    if approval.get("schema") != APPROVAL_SCHEMA:
        raise CalibrationSourceChangeVerificationError("unsupported approval schema")
    if policy.get("schema") != POLICY_SCHEMA:
        raise CalibrationSourceChangeVerificationError("unsupported source-change policy schema")

    _strict_authority(
        source_change.get("authority"),
        {
            "reviewer_approval_verified": True,
            "source_control_change_required": True,
            "runtime_write_permitted": False,
            "automatic_runtime_application": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
        "source change",
    )
    _strict_authority(
        profile.get("authority"),
        {
            "source_review_artifact_only": True,
            "runtime_write_permitted": False,
            "automatic_runtime_application": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
        "approved profile",
    )

    if source_change.get("hard_safety_limits_changed") is not False or source_change.get("runtime_files_changed") is not False:
        raise CalibrationSourceChangeVerificationError("source-change package claims runtime or hard-safety modification")
    if source_change.get("quantization_regression_pass") is not True:
        raise CalibrationSourceChangeVerificationError("source-change quantization regression did not pass")
    if source_change.get("approved_channels") != ["current", "temperature"]:
        raise CalibrationSourceChangeVerificationError("source-change approved channel set is invalid")
    if source_change.get("deferred_channels") != ["accelerometer"]:
        raise CalibrationSourceChangeVerificationError("accelerometer must remain deferred")

    package_sha = _file_sha256(change_package_dir / "change-package.json")
    if _require_hash(source_change.get("change_package_sha256"), "source_change.change_package_sha256") != package_sha:
        raise CalibrationSourceChangeVerificationError("source-change change-package hash mismatch")
    if _file_sha256(approval_path) != _require_hash(source_change.get("approval_sha256"), "source_change.approval_sha256"):
        raise CalibrationSourceChangeVerificationError("source-change approval hash mismatch")
    if _file_sha256(policy_path) != _require_hash(source_change.get("policy_sha256"), "source_change.policy_sha256"):
        raise CalibrationSourceChangeVerificationError("source-change policy hash mismatch")
    if approval.get("change_package_sha256") != package_sha:
        raise CalibrationSourceChangeVerificationError("approval is not bound to retained change package")
    for field in ("campaign_id", "repository_commit", "evidence_root_sha256"):
        if source_change.get(field) != package.get(field) or profile.get(field) != package.get(field):
            raise CalibrationSourceChangeVerificationError(f"source-change provenance field {field} is inconsistent")
    if source_change.get("approval_id") != approval.get("approval_id") or profile.get("approval_id") != approval.get("approval_id"):
        raise CalibrationSourceChangeVerificationError("source-change approval_id is inconsistent")

    if _file_sha256(change_dir / "approved-profile.json") != _require_hash(
        source_change.get("approved_profile_sha256"), "source_change.approved_profile_sha256"
    ):
        raise CalibrationSourceChangeVerificationError("approved profile hash mismatch")
    if _file_sha256(change_dir / "source-change.patch") != _require_hash(
        source_change.get("source_patch_sha256"), "source_change.source_patch_sha256"
    ):
        raise CalibrationSourceChangeVerificationError("source patch hash mismatch")
    if _file_sha256(change_dir / "safety-baseline.json") != _require_hash(
        source_change.get("safety_baseline_sha256"), "source_change.safety_baseline_sha256"
    ):
        raise CalibrationSourceChangeVerificationError("safety baseline artifact hash mismatch")

    current_regression = profile.get("quantization_regression", {}).get("current", {})
    temp_regression = profile.get("quantization_regression", {}).get("temperature", {})
    if current_regression.get("regression_pass") is not True or temp_regression.get("regression_pass") is not True:
        raise CalibrationSourceChangeVerificationError("approved profile contains a failing quantization regression")
    accelerometer = profile.get("accelerometer")
    if not isinstance(accelerometer, dict) or accelerometer.get("status") != "deferred" or accelerometer.get("runtime_mapping_supported") is not False:
        raise CalibrationSourceChangeVerificationError("approved profile must defer accelerometer correction")

    target = _safe_rel_path(source_change.get("patch_target"), "source_change.patch_target")
    configured_directory = _safe_rel_path(
        policy.get("source_patch", {}).get("approved_profile_directory"),
        "policy.source_patch.approved_profile_directory",
    )
    if target.parent != configured_directory:
        raise CalibrationSourceChangeVerificationError("source patch target is outside approved calibration profile directory")
    patch_text = (change_dir / "source-change.patch").read_text(encoding="utf-8")
    diff_headers = [line for line in patch_text.splitlines() if line.startswith("diff --git ")]
    expected_header = f"diff --git a/{target} b/{target}"
    if diff_headers != [expected_header]:
        raise CalibrationSourceChangeVerificationError("source patch must add exactly one approved profile target")
    if "--- /dev/null" not in patch_text or f"+++ b/{target}" not in patch_text:
        raise CalibrationSourceChangeVerificationError("source patch is not an add-only approved profile patch")

    if baseline.get("hard_safety_limit_change_approved") is not False:
        raise CalibrationSourceChangeVerificationError("safety baseline must forbid hard-safety limit changes")
    baseline_files = baseline.get("files")
    if not isinstance(baseline_files, list) or not baseline_files:
        raise CalibrationSourceChangeVerificationError("safety baseline has no files")
    configured_files = policy.get("safety_baseline_files")
    recorded_paths = [entry.get("path") for entry in baseline_files if isinstance(entry, dict)]
    if recorded_paths != configured_files:
        raise CalibrationSourceChangeVerificationError("safety baseline file set differs from source-change policy")
    for entry_index, entry in enumerate(baseline_files):
        relative = _safe_rel_path(entry.get("path"), f"safety_baseline.files[{entry_index}].path")
        expected = _require_hash(entry.get("sha256"), f"safety_baseline.files[{entry_index}].sha256")
        actual = _file_sha256(_confined(repo_root, relative, f"safety baseline file {entry_index}"))
        if actual != expected:
            raise CalibrationSourceChangeVerificationError(f"safety baseline changed after package generation: {relative}")

    target_path = _confined(repo_root, target, "approved profile target")
    target_state = "absent"
    if target_path.exists():
        if target_path.read_bytes() != (change_dir / "approved-profile.json").read_bytes():
            raise CalibrationSourceChangeVerificationError("existing approved profile target differs from verified profile")
        target_state = "applied_identical"

    return {
        "schema": VERIFICATION_SCHEMA,
        "campaign_id": source_change["campaign_id"],
        "repository_commit": source_change["repository_commit"],
        "approval_id": source_change["approval_id"],
        "artifact_integrity_pass": True,
        "approval_binding_pass": True,
        "quantization_regression_pass": True,
        "hard_safety_non_regression_pass": True,
        "runtime_source_unchanged": True,
        "patch_target_state": target_state,
        "artifact_root_sha256": claimed_root,
        "authority": {
            "verification_only": True,
            "runtime_write_permitted": False,
            "automatic_runtime_application": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify an approved ForgeSense calibration source-change package")
    parser.add_argument("change_dir", type=Path)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--change-package-dir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("hardware/calibration/calibration_source_change_policy_v1.json"),
    )
    parser.add_argument("--report-out", type=Path)
    args = parser.parse_args()
    try:
        result = verify_source_change(
            args.change_dir,
            approval_path=args.approval,
            change_package_dir=args.change_package_dir,
            repo_root=args.repo_root,
            policy_path=args.policy,
        )
    except CalibrationSourceChangeVerificationError as exc:
        raise SystemExit(f"calibration source-change verification failed: {exc}") from exc
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        "calibration source-change verification PASS: "
        f"quantization={result['quantization_regression_pass']} "
        f"hard_safety_non_regression={result['hard_safety_non_regression_pass']} "
        f"target_state={result['patch_target_state']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
