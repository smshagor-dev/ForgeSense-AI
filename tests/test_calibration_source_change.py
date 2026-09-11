from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.prepare_approved_calibration_source_change import (
    CalibrationSourceChangeError,
    _quantize_current,
    _quantize_temperature,
    _validate_approval,
)
from tools.verify_calibration_source_change import (
    CalibrationSourceChangeVerificationError,
    verify_source_change,
)

COMMIT = "e" * 40
ROOT_HASH = "a" * 64


def _json_bytes(data: dict) -> bytes:
    return (json.dumps(data, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha256(data: dict) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _policy() -> dict:
    return {
        "schema": "forgesense.calibration_source_change_policy.v1",
        "policy_id": "CAL-SOURCE-TEST",
        "current": {
            "maximum_gain_denominator": 1_000_000,
            "maximum_abs_quantization_error_ma": 2.0,
            "require_nonnegative_at_reference_points": True,
            "minimum_output_ma": 0,
            "maximum_output_ma": 32767,
        },
        "temperature": {
            "maximum_abs_quantization_error_c": 0.051,
            "minimum_output_deci_c": -32768,
            "maximum_output_deci_c": 32767,
        },
        "accelerometer": {
            "runtime_mapping_supported": False,
            "required_disposition": "deferred",
        },
        "source_patch": {
            "approved_profile_directory": "hardware/calibration/approved",
            "runtime_files_may_be_modified": False,
            "existing_target_may_be_overwritten": False,
        },
        "safety_baseline_files": ["safety/hard_limit_monitor.vhd"],
    }


def test_source_change_quantizes_current_against_retained_raw_points() -> None:
    candidate = {
        "mean_slope_ma_per_count_candidate": 0.0005,
        "mean_intercept_ma_candidate": 0.2,
    }
    result = _quantize_current(candidate, [0, 1_000_000, 2_000_000, 6_400_000], _policy())
    calibration = result["linear_calibration"]
    assert calibration["gain_numerator"] == 1
    assert calibration["gain_denominator"] == 2000
    assert calibration["output_offset"] == 0
    assert result["maximum_abs_quantization_error_ma"] <= 0.21
    assert result["regression_pass"] is True
    assert result["nonnegative_at_reference_points"] is True


def test_source_change_rejects_negative_current_mapping_at_reference_point() -> None:
    candidate = {
        "mean_slope_ma_per_count_candidate": 0.0005,
        "mean_intercept_ma_candidate": -2.1,
    }
    with pytest.raises(CalibrationSourceChangeError, match="current integer quantization failed regression gate"):
        _quantize_current(candidate, [0, 1_000_000, 6_400_000], _policy())


def test_temperature_quantization_is_bounded() -> None:
    candidate = {"mean_offset_c_candidate": 0.234}
    result = _quantize_temperature(candidate, _policy())
    assert result["linear_calibration"]["gain_numerator"] == 1
    assert result["linear_calibration"]["gain_denominator"] == 1
    assert result["linear_calibration"]["output_offset"] == 2
    assert abs(result["quantization_error_c"]) <= 0.051
    assert result["regression_pass"] is True


def test_approval_must_defer_unmapped_accelerometer(tmp_path: Path) -> None:
    package = {
        "campaign_id": "CAL-001",
        "repository_commit": COMMIT,
        "evidence_root_sha256": ROOT_HASH,
    }
    package_bytes = _json_bytes(package)
    approval = {
        "schema": "forgesense.calibration_approval.v1",
        "approval_id": "APR-001",
        "campaign_id": "CAL-001",
        "repository_commit": COMMIT,
        "evidence_root_sha256": ROOT_HASH,
        "change_package_sha256": _sha256(package_bytes),
        "decision": "approved_for_source_change",
        "approved_channels": ["current", "temperature", "accelerometer"],
        "deferred_channels": [],
        "reviewer": {"name": "Reviewer", "role": "Calibration Reviewer"},
        "reviewed_at_utc": "2026-09-11T18:00:00Z",
        "rationale": "Synthetic test approval only.",
        "authority_acknowledgements": {
            "source_control_change_required": True,
            "runtime_write_approved": False,
            "automatic_runtime_application": False,
            "hard_safety_limit_change_approved": False,
        },
    }
    with pytest.raises(CalibrationSourceChangeError, match="approve only current and temperature"):
        _validate_approval(approval, package, _sha256(package_bytes))


def _verification_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    repo_root = tmp_path / "repo"
    safety_file = repo_root / "safety/hard_limit_monitor.vhd"
    safety_file.parent.mkdir(parents=True)
    safety_file.write_text("hard limits frozen\n", encoding="utf-8")

    policy = _policy()
    policy_path = repo_root / "policy.json"
    policy_path.write_bytes(_json_bytes(policy))

    change_package_dir = tmp_path / "review-package"
    change_package_dir.mkdir()
    package = {
        "schema": "forgesense.calibration_change_package.v1",
        "campaign_id": "CAL-001",
        "repository_commit": COMMIT,
        "evidence_root_sha256": ROOT_HASH,
    }
    package_bytes = _json_bytes(package)
    (change_package_dir / "change-package.json").write_bytes(package_bytes)
    package_sha = _sha256(package_bytes)

    approval = {
        "schema": "forgesense.calibration_approval.v1",
        "approval_id": "APR-001",
        "campaign_id": "CAL-001",
        "repository_commit": COMMIT,
        "evidence_root_sha256": ROOT_HASH,
        "change_package_sha256": package_sha,
    }
    approval_path = tmp_path / "approval.json"
    approval_path.write_bytes(_json_bytes(approval))

    target = "hardware/calibration/approved/CAL-001.json"
    profile = {
        "schema": "forgesense.approved_calibration_source_profile.v1",
        "approval_id": "APR-001",
        "campaign_id": "CAL-001",
        "repository_commit": COMMIT,
        "evidence_root_sha256": ROOT_HASH,
        "change_package_sha256": package_sha,
        "accelerometer": {
            "status": "deferred",
            "runtime_mapping_supported": False,
        },
        "quantization_regression": {
            "current": {"regression_pass": True},
            "temperature": {"regression_pass": True},
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
    patch_bytes = (
        f"diff --git a/{target} b/{target}\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        f"+++ b/{target}\n"
        "@@ -0,0 +1,1 @@\n"
        "+synthetic\n"
    ).encode("utf-8")
    baseline = {
        "schema": "forgesense.calibration_safety_baseline.v1",
        "policy_id": policy["policy_id"],
        "hard_safety_limit_change_approved": False,
        "files": [
            {
                "path": "safety/hard_limit_monitor.vhd",
                "sha256": _sha256(safety_file.read_bytes()),
            }
        ],
    }
    baseline_bytes = _json_bytes(baseline)
    source_change = {
        "schema": "forgesense.calibration_source_change.v1",
        "approval_id": "APR-001",
        "campaign_id": "CAL-001",
        "repository_commit": COMMIT,
        "evidence_root_sha256": ROOT_HASH,
        "change_package_sha256": package_sha,
        "approval_sha256": _sha256(approval_path.read_bytes()),
        "policy_id": policy["policy_id"],
        "policy_sha256": _sha256(policy_path.read_bytes()),
        "patch_target": target,
        "approved_profile_sha256": _sha256(profile_bytes),
        "source_patch_sha256": _sha256(patch_bytes),
        "safety_baseline_sha256": _sha256(baseline_bytes),
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
    }
    source_change_bytes = _json_bytes(source_change)

    change_dir = tmp_path / "source-change"
    change_dir.mkdir()
    artifact_bytes = {
        "approved-profile.json": profile_bytes,
        "safety-baseline.json": baseline_bytes,
        "source-change.json": source_change_bytes,
        "source-change.patch": patch_bytes,
    }
    for path, content in artifact_bytes.items():
        (change_dir / path).write_bytes(content)
    index_core = {
        "schema": "forgesense.calibration_source_change_artifact_index.v1",
        "campaign_id": "CAL-001",
        "repository_commit": COMMIT,
        "artifacts": [
            {"path": path, "sha256": _sha256(content)}
            for path, content in sorted(artifact_bytes.items())
        ],
        "authority": {
            "integrity_index_only": True,
            "runtime_write_permitted": False,
            "may_relax_hard_safety_limits": False,
        },
    }
    index = dict(index_core)
    index["root_sha256"] = _canonical_sha256(index_core)
    (change_dir / "artifact-index.json").write_bytes(_json_bytes(index))
    return change_dir, approval_path, change_package_dir, repo_root, policy_path


def test_source_change_verifier_accepts_preapply_package(tmp_path: Path) -> None:
    change_dir, approval, package_dir, repo_root, policy = _verification_fixture(tmp_path)
    result = verify_source_change(
        change_dir,
        approval_path=approval,
        change_package_dir=package_dir,
        repo_root=repo_root,
        policy_path=policy,
    )
    assert result["artifact_integrity_pass"] is True
    assert result["quantization_regression_pass"] is True
    assert result["hard_safety_non_regression_pass"] is True
    assert result["runtime_source_unchanged"] is True
    assert result["patch_target_state"] == "absent"


def test_source_change_verifier_rejects_patch_tamper(tmp_path: Path) -> None:
    change_dir, approval, package_dir, repo_root, policy = _verification_fixture(tmp_path)
    (change_dir / "source-change.patch").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(CalibrationSourceChangeVerificationError, match="artifact hash mismatch"):
        verify_source_change(
            change_dir,
            approval_path=approval,
            change_package_dir=package_dir,
            repo_root=repo_root,
            policy_path=policy,
        )


def test_source_change_verifier_rejects_safety_baseline_drift(tmp_path: Path) -> None:
    change_dir, approval, package_dir, repo_root, policy = _verification_fixture(tmp_path)
    (repo_root / "safety/hard_limit_monitor.vhd").write_text("changed hard limits\n", encoding="utf-8")
    with pytest.raises(CalibrationSourceChangeVerificationError, match="safety baseline changed"):
        verify_source_change(
            change_dir,
            approval_path=approval,
            change_package_dir=package_dir,
            repo_root=repo_root,
            policy_path=policy,
        )


def test_source_change_verifier_accepts_applied_identical_profile(tmp_path: Path) -> None:
    change_dir, approval, package_dir, repo_root, policy = _verification_fixture(tmp_path)
    target = repo_root / "hardware/calibration/approved/CAL-001.json"
    target.parent.mkdir(parents=True)
    target.write_bytes((change_dir / "approved-profile.json").read_bytes())
    result = verify_source_change(
        change_dir,
        approval_path=approval,
        change_package_dir=package_dir,
        repo_root=repo_root,
        policy_path=policy,
    )
    assert result["patch_target_state"] == "applied_identical"
