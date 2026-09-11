from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import mean

HEX40 = re.compile(r"^[0-9a-fA-F]{40}$")
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def _linear_fit(points: list[tuple[float, float]]) -> dict[str, float]:
    if len(points) < 2:
        raise ValueError("linear fit requires at least two points")
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    xbar = mean(xs)
    ybar = mean(ys)
    denom = sum((x - xbar) ** 2 for x in xs)
    if denom <= 0:
        raise ValueError("calibration x values have no span")
    slope = sum((x - xbar) * (y - ybar) for x, y in points) / denom
    intercept = ybar - slope * xbar
    predicted = [slope * x + intercept for x in xs]
    residuals = [y - p for y, p in zip(ys, predicted)]
    ss_res = sum(r * r for r in residuals)
    ss_tot = sum((y - ybar) ** 2 for y in ys)
    return {
        "slope": slope,
        "intercept": intercept,
        "rmse": math.sqrt(ss_res / len(points)),
        "max_abs_residual": max(abs(r) for r in residuals),
        "r2": 1.0 if ss_tot == 0 and ss_res == 0 else (1.0 - ss_res / ss_tot if ss_tot else 0.0),
        "x_span": max(xs) - min(xs),
    }


def _require_hash(value: str, label: str) -> str:
    if not HEX64.fullmatch(value):
        raise ValueError(f"{label} must be a 64-hex SHA-256")
    return value.lower()


def _validate_capture(data: dict) -> None:
    required = ["schema", "capture_id", "repository_commit", "boards", "instruments", "evidence", "current", "temperature", "accelerometer"]
    for key in required:
        if key not in data:
            raise ValueError(f"missing required field {key!r}")
    if data["schema"] != "forgesense.calibration_capture.v1":
        raise ValueError("unsupported calibration capture schema")
    if not HEX40.fullmatch(str(data["repository_commit"])):
        raise ValueError("repository_commit must be a full 40-hex SHA")
    for key in ("fpga_revision", "esp32_revision", "sensor_board_revision"):
        if not str(data["boards"].get(key, "")).strip():
            raise ValueError(f"boards.{key} is required")
    if not data["instruments"]:
        raise ValueError("at least one instrument is required")
    for item in data["evidence"]:
        _require_hash(str(item.get("sha256", "")), "evidence.sha256")
    if len(data["current"].get("points", [])) < 5:
        raise ValueError("current calibration requires at least five points")
    if len(data["temperature"].get("points", [])) < 3:
        raise ValueError("temperature characterization requires at least three points")
    if len(data["accelerometer"].get("stationary_samples_mg", [])) < 20:
        raise ValueError("accelerometer characterization requires at least 20 stationary samples")


def build_proposal(data: dict) -> dict:
    _validate_capture(data)

    current_points = [
        (float(p["adc_raw"]), float(p["reference_current_a"]) * 1000.0)
        for p in data["current"]["points"]
    ]
    current_fit = _linear_fit(current_points)
    current_fraction = Fraction(current_fit["slope"]).limit_denominator(1_000_000)
    current_quality = (
        current_fit["x_span"] >= float(data["current"].get("minimum_raw_span", 100000.0))
        and current_fit["r2"] >= float(data["current"].get("minimum_r2", 0.999))
        and current_fit["rmse"] <= float(data["current"].get("maximum_rmse_ma", 50.0))
    )

    temp_deltas = [
        float(p["reference_temperature_c"]) - float(p["tmp117_temperature_c"])
        for p in data["temperature"]["points"]
    ]
    temp_offset_c = mean(temp_deltas)
    temp_residuals = [d - temp_offset_c for d in temp_deltas]
    temp_rmse_c = math.sqrt(mean([r * r for r in temp_residuals]))
    temp_quality = temp_rmse_c <= float(data["temperature"].get("maximum_offset_rmse_c", 0.20))

    accel_samples = data["accelerometer"]["stationary_samples_mg"]
    axes = {
        axis: mean(float(sample[axis]) for sample in accel_samples)
        for axis in ("x", "y", "z")
    }
    expected = data["accelerometer"].get("expected_stationary_mg", {"x": 0.0, "y": 0.0, "z": 1000.0})
    biases = {axis: axes[axis] - float(expected[axis]) for axis in axes}
    max_bias = max(abs(v) for v in biases.values())
    accel_quality = max_bias <= float(data["accelerometer"].get("maximum_abs_bias_mg", 250.0))

    proposal = {
        "schema": "forgesense.calibration_proposal.v1",
        "source_capture_id": data["capture_id"],
        "repository_commit": data["repository_commit"].lower(),
        "authority": {
            "review_required": True,
            "automatic_runtime_application": False,
            "may_relax_hard_safety_limits": False,
            "note": "This artifact is evidence-derived engineering input only. It does not modify FPGA or ESP32 runtime calibration."
        },
        "provenance": {
            "boards": data["boards"],
            "instruments": data["instruments"],
            "environment": data.get("environment", {}),
            "evidence": data["evidence"],
        },
        "current": {
            "fit_target": "adc_raw_to_current_milli_a",
            "points": len(current_points),
            "slope_ma_per_count": current_fit["slope"],
            "intercept_ma": current_fit["intercept"],
            "rmse_ma": current_fit["rmse"],
            "max_abs_residual_ma": current_fit["max_abs_residual"],
            "r2": current_fit["r2"],
            "raw_span": current_fit["x_span"],
            "integer_candidate": {
                "gain_numerator": current_fraction.numerator,
                "gain_denominator": current_fraction.denominator,
                "output_offset_ma": round(current_fit["intercept"]),
            },
            "proposal_quality_pass": current_quality,
        },
        "temperature": {
            "method": "constant_offset_characterization",
            "points": len(temp_deltas),
            "offset_c": temp_offset_c,
            "offset_deci_c_candidate": round(temp_offset_c * 10.0),
            "residual_rmse_c": temp_rmse_c,
            "max_abs_residual_c": max(abs(r) for r in temp_residuals),
            "proposal_quality_pass": temp_quality,
        },
        "accelerometer": {
            "method": "stationary_axis_bias_characterization",
            "samples": len(accel_samples),
            "expected_stationary_mg": expected,
            "mean_measured_mg": axes,
            "bias_mg": biases,
            "correction_mg_candidate": {axis: -round(value) for axis, value in biases.items()},
            "maximum_abs_bias_mg": max_bias,
            "proposal_quality_pass": accel_quality,
        },
    }
    proposal["proposal_quality_pass"] = current_quality and temp_quality and accel_quality
    return proposal


def _canonical_sha256(data: dict) -> str:
    blob = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a review-only ForgeSense bench calibration proposal")
    parser.add_argument("capture", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    capture = json.loads(args.capture.read_text(encoding="utf-8"))
    proposal = build_proposal(capture)
    proposal["source_capture_sha256"] = _canonical_sha256(capture)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(proposal, indent=2) + "\n", encoding="utf-8")
    print(f"calibration proposal written: {args.out}; quality_pass={proposal['proposal_quality_pass']}")
    return 0 if proposal["proposal_quality_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
