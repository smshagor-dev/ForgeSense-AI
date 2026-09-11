from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import mean

HEX40 = re.compile(r"^[0-9a-fA-F]{40}$")
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
AXES = ("x", "y", "z")


def _canonical_sha256(data: dict) -> str:
    blob = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _finite(value: object, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _nonnegative(value: object, label: str) -> float:
    result = _finite(value, label)
    if result < 0:
        raise ValueError(f"{label} must be non-negative")
    return result


def _policy_number(section: dict, key: str, label: str) -> float:
    if key not in section:
        raise ValueError(f"missing policy field {label}.{key}")
    return _nonnegative(section[key], f"{label}.{key}")


def _validate_policy(policy: dict) -> None:
    if policy.get("schema") != "forgesense.calibration_review_policy.v1":
        raise ValueError("unsupported calibration review policy schema")
    minimum_runs = int(policy.get("minimum_runs", 0))
    if minimum_runs < 2:
        raise ValueError("minimum_runs must be at least 2")
    for section_name in ("current", "temperature", "accelerometer", "uncertainty"):
        if not isinstance(policy.get(section_name), dict):
            raise ValueError(f"missing policy section {section_name}")

    for key in ("maximum_slope_span_ppm", "maximum_intercept_span_ma", "maximum_run_rmse_ma"):
        _policy_number(policy["current"], key, "current")
    for key in ("maximum_offset_span_c", "maximum_run_residual_rmse_c"):
        _policy_number(policy["temperature"], key, "temperature")
    for key in ("maximum_axis_bias_span_mg", "maximum_run_axis_stddev_mg", "maximum_abs_bias_mg"):
        _policy_number(policy["accelerometer"], key, "accelerometer")
    for key in (
        "maximum_reference_current_ma_k2",
        "maximum_reference_temperature_c_k2",
        "maximum_reference_accelerometer_mg_k2",
    ):
        _policy_number(policy["uncertainty"], key, "uncertainty")


def _validate_proposal(proposal: dict, index: int) -> None:
    prefix = f"proposal[{index}]"
    if proposal.get("schema") != "forgesense.calibration_proposal.v1":
        raise ValueError(f"{prefix} has unsupported schema")
    commit = str(proposal.get("repository_commit", ""))
    if not HEX40.fullmatch(commit):
        raise ValueError(f"{prefix}.repository_commit must be a full 40-hex SHA")
    source_hash = str(proposal.get("source_capture_sha256", ""))
    if not HEX64.fullmatch(source_hash):
        raise ValueError(f"{prefix}.source_capture_sha256 must be a 64-hex SHA-256")

    authority = proposal.get("authority", {})
    if authority.get("review_required") is not True:
        raise ValueError(f"{prefix} must require review")
    if authority.get("automatic_runtime_application") is not False:
        raise ValueError(f"{prefix} must forbid automatic runtime application")
    if authority.get("may_relax_hard_safety_limits") is not False:
        raise ValueError(f"{prefix} must forbid relaxing hard safety limits")

    provenance = proposal.get("provenance", {})
    boards = provenance.get("boards", {})
    for key in ("fpga_revision", "esp32_revision", "sensor_board_revision"):
        if not str(boards.get(key, "")).strip():
            raise ValueError(f"{prefix}.provenance.boards.{key} is required")

    for section in ("current", "temperature", "accelerometer"):
        if not isinstance(proposal.get(section), dict):
            raise ValueError(f"{prefix} is missing {section}")


def _same_mapping(values: list[dict]) -> bool:
    canonical = {json.dumps(value, sort_keys=True, separators=(",", ":")) for value in values}
    return len(canonical) == 1


def _uncertainty_values(proposals: list[dict], key: str) -> tuple[list[float], bool]:
    values: list[float] = []
    complete = True
    for index, proposal in enumerate(proposals):
        uncertainty = proposal["provenance"].get("measurement_uncertainty", {})
        if key not in uncertainty:
            complete = False
            continue
        values.append(_nonnegative(uncertainty[key], f"proposal[{index}].provenance.measurement_uncertainty.{key}"))
    return values, complete and len(values) == len(proposals)


def _engineering_k2_proxy(residual_sigma: float, reference_k2: float, repeatability_half_span: float = 0.0) -> float:
    reference_sigma = reference_k2 / 2.0
    combined_sigma = math.sqrt(
        residual_sigma * residual_sigma
        + reference_sigma * reference_sigma
        + repeatability_half_span * repeatability_half_span
    )
    return 2.0 * combined_sigma


def review_proposals(proposals: list[dict], policy: dict) -> dict:
    _validate_policy(policy)
    if not proposals:
        raise ValueError("at least one calibration proposal is required")
    for index, proposal in enumerate(proposals):
        _validate_proposal(proposal, index)

    minimum_runs = int(policy["minimum_runs"])
    run_count_pass = len(proposals) >= minimum_runs
    proposal_quality_pass = all(proposal.get("proposal_quality_pass") is True for proposal in proposals)

    boards = [proposal["provenance"]["boards"] for proposal in proposals]
    board_consistent = _same_mapping(boards)
    commits = [proposal["repository_commit"].lower() for proposal in proposals]
    commit_consistent = len(set(commits)) == 1

    require_same_boards = bool(policy.get("require_same_board_revisions", True))
    require_same_commit = bool(policy.get("require_same_repository_commit", True))
    board_gate = board_consistent or not require_same_boards
    commit_gate = commit_consistent or not require_same_commit

    current_slopes = [_finite(p["current"]["slope_ma_per_count"], "current.slope_ma_per_count") for p in proposals]
    current_intercepts = [_finite(p["current"]["intercept_ma"], "current.intercept_ma") for p in proposals]
    current_rmse = [_nonnegative(p["current"]["rmse_ma"], "current.rmse_ma") for p in proposals]
    slope_mean = mean(current_slopes)
    if slope_mean == 0:
        slope_span_ppm: float | None = None
    else:
        slope_span_ppm = (max(current_slopes) - min(current_slopes)) / abs(slope_mean) * 1_000_000.0
    intercept_span_ma = max(current_intercepts) - min(current_intercepts)
    current_repeatability_pass = (
        slope_span_ppm is not None
        and slope_span_ppm <= float(policy["current"]["maximum_slope_span_ppm"])
        and intercept_span_ma <= float(policy["current"]["maximum_intercept_span_ma"])
        and max(current_rmse) <= float(policy["current"]["maximum_run_rmse_ma"])
    )

    temp_offsets = [_finite(p["temperature"]["offset_c"], "temperature.offset_c") for p in proposals]
    temp_rmse = [_nonnegative(p["temperature"]["residual_rmse_c"], "temperature.residual_rmse_c") for p in proposals]
    temp_offset_span_c = max(temp_offsets) - min(temp_offsets)
    temperature_repeatability_pass = (
        temp_offset_span_c <= float(policy["temperature"]["maximum_offset_span_c"])
        and max(temp_rmse) <= float(policy["temperature"]["maximum_run_residual_rmse_c"])
    )

    accel_bias = {
        axis: [_finite(p["accelerometer"]["bias_mg"][axis], f"accelerometer.bias_mg.{axis}") for p in proposals]
        for axis in AXES
    }
    accel_stddev = {
        axis: [_nonnegative(p["accelerometer"].get("axis_stddev_mg", {}).get(axis, math.inf), f"accelerometer.axis_stddev_mg.{axis}") for p in proposals]
        for axis in AXES
    }
    axis_bias_span = {axis: max(values) - min(values) for axis, values in accel_bias.items()}
    max_abs_bias = max(abs(value) for values in accel_bias.values() for value in values)
    max_axis_stddev = max(value for values in accel_stddev.values() for value in values)
    accelerometer_repeatability_pass = (
        max(axis_bias_span.values()) <= float(policy["accelerometer"]["maximum_axis_bias_span_mg"])
        and max_axis_stddev <= float(policy["accelerometer"]["maximum_run_axis_stddev_mg"])
        and max_abs_bias <= float(policy["accelerometer"]["maximum_abs_bias_mg"])
    )

    current_uncertainty, current_uncertainty_complete = _uncertainty_values(proposals, "reference_current_ma_k2")
    temp_uncertainty, temp_uncertainty_complete = _uncertainty_values(proposals, "reference_temperature_c_k2")
    accel_uncertainty, accel_uncertainty_complete = _uncertainty_values(proposals, "reference_accelerometer_mg_k2")
    uncertainty_complete = current_uncertainty_complete and temp_uncertainty_complete and accel_uncertainty_complete
    require_uncertainty = bool(policy["uncertainty"].get("require_declared", True))
    uncertainty_limits_pass = (
        uncertainty_complete
        and max(current_uncertainty) <= float(policy["uncertainty"]["maximum_reference_current_ma_k2"])
        and max(temp_uncertainty) <= float(policy["uncertainty"]["maximum_reference_temperature_c_k2"])
        and max(accel_uncertainty) <= float(policy["uncertainty"]["maximum_reference_accelerometer_mg_k2"])
    )
    uncertainty_gate = uncertainty_limits_pass if require_uncertainty else (uncertainty_limits_pass or not uncertainty_complete)

    current_reference_k2: float | None = max(current_uncertainty) if current_uncertainty else None
    temp_reference_k2: float | None = max(temp_uncertainty) if temp_uncertainty else None
    accel_reference_k2: float | None = max(accel_uncertainty) if accel_uncertainty else None

    review_ready = all(
        (
            run_count_pass,
            proposal_quality_pass,
            board_gate,
            commit_gate,
            current_repeatability_pass,
            temperature_repeatability_pass,
            accelerometer_repeatability_pass,
            uncertainty_gate,
        )
    )

    result = {
        "schema": "forgesense.calibration_review.v1",
        "policy_id": str(policy.get("policy_id", "")),
        "source_capture_ids": [str(p.get("source_capture_id", "")) for p in proposals],
        "source_proposal_sha256": [_canonical_sha256(p) for p in proposals],
        "authority": {
            "reviewer_approval_required": True,
            "source_control_change_required": True,
            "automatic_runtime_application": False,
            "may_relax_hard_safety_limits": False,
            "note": "Review-ready means the evidence is internally consistent enough for engineering review. It is not authorization to change runtime calibration or safety limits.",
        },
        "provenance": {
            "run_count": len(proposals),
            "minimum_runs": minimum_runs,
            "run_count_pass": run_count_pass,
            "board_revisions_consistent": board_consistent,
            "repository_commit_consistent": commit_consistent,
            "repository_commits": sorted(set(commits)),
            "measurement_uncertainty_complete": uncertainty_complete,
        },
        "current": {
            "mean_slope_ma_per_count_candidate": slope_mean,
            "slope_span_ppm": slope_span_ppm,
            "mean_intercept_ma_candidate": mean(current_intercepts),
            "intercept_span_ma": intercept_span_ma,
            "maximum_run_rmse_ma": max(current_rmse),
            "maximum_reference_uncertainty_ma_k2": current_reference_k2,
            "engineering_uncertainty_proxy_ma_k2": (
                _engineering_k2_proxy(max(current_rmse), current_reference_k2, intercept_span_ma / 2.0)
                if current_reference_k2 is not None
                else None
            ),
            "repeatability_pass": current_repeatability_pass,
        },
        "temperature": {
            "mean_offset_c_candidate": mean(temp_offsets),
            "offset_span_c": temp_offset_span_c,
            "maximum_run_residual_rmse_c": max(temp_rmse),
            "maximum_reference_uncertainty_c_k2": temp_reference_k2,
            "engineering_uncertainty_proxy_c_k2": (
                _engineering_k2_proxy(max(temp_rmse), temp_reference_k2, temp_offset_span_c / 2.0)
                if temp_reference_k2 is not None
                else None
            ),
            "repeatability_pass": temperature_repeatability_pass,
        },
        "accelerometer": {
            "mean_bias_mg_candidate": {axis: mean(values) for axis, values in accel_bias.items()},
            "axis_bias_span_mg": axis_bias_span,
            "maximum_run_axis_stddev_mg": max_axis_stddev,
            "maximum_abs_bias_mg": max_abs_bias,
            "maximum_reference_uncertainty_mg_k2": accel_reference_k2,
            "engineering_uncertainty_proxy_mg_k2": (
                _engineering_k2_proxy(max_axis_stddev, accel_reference_k2, max(axis_bias_span.values()) / 2.0)
                if accel_reference_k2 is not None
                else None
            ),
            "repeatability_pass": accelerometer_repeatability_pass,
        },
        "checks": {
            "proposal_quality_pass": proposal_quality_pass,
            "board_gate_pass": board_gate,
            "commit_gate_pass": commit_gate,
            "uncertainty_limits_pass": uncertainty_limits_pass,
        },
        "review_ready": review_ready,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Review repeated ForgeSense calibration proposals without applying them")
    parser.add_argument("proposals", nargs="+", type=Path)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    proposals = [json.loads(path.read_text(encoding="utf-8")) for path in args.proposals]
    result = review_proposals(proposals, policy)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"calibration review written: {args.out}; review_ready={result['review_ready']}")
    return 0 if result["review_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
