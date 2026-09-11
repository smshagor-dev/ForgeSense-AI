from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import mean, pstdev

from tools.capture_calibration import build_proposal

HEX40 = re.compile(r"^[0-9a-fA-F]{40}$")
DIAGNOSTIC_SCHEMA = "forgesense.calibration_diagnostic_capture.v1"
SESSION_SCHEMA = "forgesense.calibration_session.v1"
CAPTURE_SCHEMA = "forgesense.calibration_capture.v1"


class CalibrationAssemblyError(ValueError):
    pass


def _finite(value: object, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise CalibrationAssemblyError(f"{label} must be finite")
    return result


def _nonnegative(value: object, label: str) -> float:
    result = _finite(value, label)
    if result < 0:
        raise CalibrationAssemblyError(f"{label} must be non-negative")
    return result


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(data: dict) -> str:
    blob = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _resolve(base_dir: Path, value: object, label: str) -> Path:
    text = str(value or "").strip()
    if not text:
        raise CalibrationAssemblyError(f"{label} is required")
    path = Path(text)
    return path if path.is_absolute() else base_dir / path


def _diagnostic_result(raw: dict, path: Path) -> dict:
    if raw.get("mode") == "calibration" and isinstance(raw.get("result"), dict):
        result = raw["result"]
    else:
        result = raw

    if result.get("schema") != DIAGNOSTIC_SCHEMA:
        raise CalibrationAssemblyError(f"{path}: unsupported diagnostic schema")
    authority = result.get("authority", {})
    required_authority = {
        "read_only": True,
        "may_control_actuators": False,
        "may_apply_calibration": False,
        "may_relax_hard_safety_limits": False,
    }
    for key, expected in required_authority.items():
        if authority.get(key) is not expected:
            raise CalibrationAssemblyError(f"{path}: diagnostic authority field {key} is invalid")
    if result.get("capture_pass") is not True:
        raise CalibrationAssemblyError(f"{path}: diagnostic capture did not pass")
    if int(result.get("sequence_gaps", 0)) != 0 or int(result.get("sequence_faults", 0)) != 0:
        raise CalibrationAssemblyError(f"{path}: diagnostic sequence integrity failed")
    if int(result.get("crc_or_frame_errors", 0)) != 0:
        raise CalibrationAssemblyError(f"{path}: diagnostic CRC/frame integrity failed")

    samples = result.get("samples")
    if not isinstance(samples, list) or not samples:
        raise CalibrationAssemblyError(f"{path}: diagnostic capture contains no samples")
    usable = [sample for sample in samples if sample.get("usable_for_calibration") is True]
    if not usable:
        raise CalibrationAssemblyError(f"{path}: diagnostic capture contains no trusted usable samples")
    return {"result": result, "usable": usable}


def _load_diagnostic(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CalibrationAssemblyError(f"diagnostic file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CalibrationAssemblyError(f"diagnostic file is not valid JSON: {path}") from exc
    if not isinstance(raw, dict):
        raise CalibrationAssemblyError(f"diagnostic file must contain a JSON object: {path}")
    return _diagnostic_result(raw, path)


def _sample_number(sample: dict, key: str, label: str) -> float:
    if key not in sample:
        raise CalibrationAssemblyError(f"{label}: missing {key}")
    return _finite(sample[key], f"{label}.{key}")


def _sample_axis(sample: dict, axis: str, label: str) -> float:
    vector = sample.get("adxl355_milli_g")
    if not isinstance(vector, dict) or axis not in vector:
        raise CalibrationAssemblyError(f"{label}: missing adxl355_milli_g.{axis}")
    return _finite(vector[axis], f"{label}.adxl355_milli_g.{axis}")


def _validate_manifest(manifest: dict) -> None:
    if manifest.get("schema") != SESSION_SCHEMA:
        raise CalibrationAssemblyError("unsupported calibration session schema")
    if not str(manifest.get("capture_id", "")).strip():
        raise CalibrationAssemblyError("capture_id is required")
    if not HEX40.fullmatch(str(manifest.get("repository_commit", ""))):
        raise CalibrationAssemblyError("repository_commit must be a full 40-hex SHA")

    boards = manifest.get("boards")
    if not isinstance(boards, dict):
        raise CalibrationAssemblyError("boards is required")
    for key in ("fpga_revision", "esp32_revision", "sensor_board_revision"):
        if not str(boards.get(key, "")).strip():
            raise CalibrationAssemblyError(f"boards.{key} is required")

    instruments = manifest.get("instruments")
    if not isinstance(instruments, list) or not instruments:
        raise CalibrationAssemblyError("at least one independent reference instrument is required")

    uncertainty = manifest.get("measurement_uncertainty")
    if not isinstance(uncertainty, dict):
        raise CalibrationAssemblyError("measurement_uncertainty is required")
    for key in (
        "reference_current_ma_k2",
        "reference_temperature_c_k2",
        "reference_accelerometer_mg_k2",
    ):
        if key not in uncertainty:
            raise CalibrationAssemblyError(f"measurement_uncertainty.{key} is required")
        _nonnegative(uncertainty[key], f"measurement_uncertainty.{key}")

    current_points = manifest.get("current", {}).get("points", [])
    temperature_points = manifest.get("temperature", {}).get("points", [])
    accel_files = manifest.get("accelerometer", {}).get("diagnostic_files", [])
    if len(current_points) < 5:
        raise CalibrationAssemblyError("session requires at least five independent current reference points")
    if len(temperature_points) < 3:
        raise CalibrationAssemblyError("session requires at least three independent temperature reference points")
    if not accel_files:
        raise CalibrationAssemblyError("session requires at least one stationary accelerometer diagnostic file")

    for section, entries in (("current", current_points), ("temperature", temperature_points)):
        seen: set[str] = set()
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise CalibrationAssemblyError(f"{section}.points[{index}] must be an object")
            source = str(entry.get("diagnostic_file", "")).strip()
            if not source:
                raise CalibrationAssemblyError(f"{section}.points[{index}].diagnostic_file is required")
            if source in seen:
                raise CalibrationAssemblyError(f"{section} reuses diagnostic file {source!r} within the same characterization")
            seen.add(source)

    for index, entry in enumerate(current_points):
        _nonnegative(entry.get("reference_current_a"), f"current.points[{index}].reference_current_a")
    for index, entry in enumerate(temperature_points):
        _finite(entry.get("reference_temperature_c"), f"temperature.points[{index}].reference_temperature_c")


def _evidence_entry(path: Path, base_dir: Path, description: str) -> dict:
    try:
        display_path = str(path.relative_to(base_dir))
    except ValueError:
        display_path = str(path)
    return {
        "file": display_path,
        "sha256": _sha256_file(path),
        "description": description,
    }


def assemble_capture(manifest: dict, *, base_dir: Path) -> dict:
    _validate_manifest(manifest)
    cache: dict[Path, dict] = {}
    evidence: dict[Path, dict] = {}

    def diagnostic(value: object, description: str) -> tuple[Path, dict]:
        path = _resolve(base_dir, value, "diagnostic_file").resolve()
        if path not in cache:
            cache[path] = _load_diagnostic(path)
        if path not in evidence:
            evidence[path] = _evidence_entry(path, base_dir.resolve(), description)
        return path, cache[path]

    current_points: list[dict] = []
    for index, entry in enumerate(manifest["current"]["points"]):
        path, capture = diagnostic(entry["diagnostic_file"], "Read-only FPGA diagnostic evidence used for current characterization")
        raw_values = [
            _sample_number(sample, "ads_ch0_raw", f"{path}:sample[{sample_index}]")
            for sample_index, sample in enumerate(capture["usable"])
        ]
        current_points.append(
            {
                "adc_raw": mean(raw_values),
                "reference_current_a": _nonnegative(entry["reference_current_a"], f"current.points[{index}].reference_current_a"),
                "diagnostic_file": evidence[path]["file"],
                "sample_count": len(raw_values),
                "adc_raw_stddev": pstdev(raw_values) if len(raw_values) > 1 else 0.0,
            }
        )

    temperature_points: list[dict] = []
    for index, entry in enumerate(manifest["temperature"]["points"]):
        path, capture = diagnostic(entry["diagnostic_file"], "Read-only FPGA diagnostic evidence used for temperature characterization")
        values = [
            _sample_number(sample, "tmp117_temperature_c", f"{path}:sample[{sample_index}]")
            for sample_index, sample in enumerate(capture["usable"])
        ]
        temperature_points.append(
            {
                "tmp117_temperature_c": mean(values),
                "reference_temperature_c": _finite(entry["reference_temperature_c"], f"temperature.points[{index}].reference_temperature_c"),
                "diagnostic_file": evidence[path]["file"],
                "sample_count": len(values),
                "tmp117_stddev_c": pstdev(values) if len(values) > 1 else 0.0,
            }
        )

    accel_samples: list[dict] = []
    accel_sources: list[dict] = []
    for source_index, value in enumerate(manifest["accelerometer"]["diagnostic_files"]):
        path, capture = diagnostic(value, "Read-only FPGA diagnostic evidence used for stationary accelerometer characterization")
        start = len(accel_samples)
        for sample_index, sample in enumerate(capture["usable"]):
            accel_samples.append(
                {
                    "x": _sample_axis(sample, "x", f"{path}:sample[{sample_index}]"),
                    "y": _sample_axis(sample, "y", f"{path}:sample[{sample_index}]"),
                    "z": _sample_axis(sample, "z", f"{path}:sample[{sample_index}]"),
                }
            )
        accel_sources.append(
            {
                "diagnostic_file": evidence[path]["file"],
                "sample_start": start,
                "sample_count": len(capture["usable"]),
                "source_index": source_index,
            }
        )

    if len(accel_samples) < 20:
        raise CalibrationAssemblyError("stationary accelerometer evidence must provide at least 20 trusted samples")

    quality = manifest.get("quality_limits", {})
    current_quality = quality.get("current", {})
    temp_quality = quality.get("temperature", {})
    accel_quality = quality.get("accelerometer", {})
    expected = manifest["accelerometer"].get("expected_stationary_mg", {"x": 0.0, "y": 0.0, "z": 1000.0})
    for axis in ("x", "y", "z"):
        _finite(expected.get(axis), f"accelerometer.expected_stationary_mg.{axis}")

    capture = {
        "schema": CAPTURE_SCHEMA,
        "capture_id": manifest["capture_id"],
        "repository_commit": str(manifest["repository_commit"]).lower(),
        "boards": manifest["boards"],
        "instruments": manifest["instruments"],
        "environment": manifest.get("environment", {}),
        "measurement_uncertainty": manifest["measurement_uncertainty"],
        "authority": {
            "assembled_from_read_only_diagnostics": True,
            "independent_reference_values_required": True,
            "automatic_runtime_application": False,
            "may_relax_hard_safety_limits": False,
        },
        "evidence": list(evidence.values()),
        "current": {
            "minimum_raw_span": float(current_quality.get("minimum_raw_span", 100000.0)),
            "minimum_r2": float(current_quality.get("minimum_r2", 0.999)),
            "maximum_rmse_ma": float(current_quality.get("maximum_rmse_ma", 50.0)),
            "points": current_points,
        },
        "temperature": {
            "maximum_offset_rmse_c": float(temp_quality.get("maximum_offset_rmse_c", 0.20)),
            "points": temperature_points,
        },
        "accelerometer": {
            "expected_stationary_mg": {axis: float(expected[axis]) for axis in ("x", "y", "z")},
            "maximum_abs_bias_mg": float(accel_quality.get("maximum_abs_bias_mg", 250.0)),
            "stationary_samples_mg": accel_samples,
            "source_diagnostics": accel_sources,
        },
        "assembly": {
            "schema": SESSION_SCHEMA,
            "diagnostic_files": len(evidence),
            "current_reference_points": len(current_points),
            "temperature_reference_points": len(temperature_points),
            "accelerometer_samples": len(accel_samples),
            "note": "ForgeSense diagnostics supply observations only; reference truth is supplied independently in the session manifest.",
        },
    }

    # Reuse the proposal builder as a structural/arithmetical compatibility check.
    # A low-quality fit remains valid evidence and is reported later as quality=false.
    build_proposal(capture)
    return capture


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble ForgeSense calibration capture evidence from read-only diagnostics and independent reference measurements")
    parser.add_argument("session", type=Path, help="forgesense.calibration_session.v1 manifest")
    parser.add_argument("--out", type=Path, required=True, help="output forgesense.calibration_capture.v1 JSON")
    parser.add_argument("--proposal-out", type=Path, help="optional review-only calibration proposal generated from the assembled capture")
    args = parser.parse_args()

    manifest = json.loads(args.session.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise SystemExit("session manifest must contain a JSON object")
    capture = assemble_capture(manifest, base_dir=args.session.parent)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(capture, indent=2) + "\n", encoding="utf-8")
    print(f"calibration capture written: {args.out}")

    if args.proposal_out:
        proposal = build_proposal(capture)
        proposal["source_capture_sha256"] = _canonical_sha256(capture)
        args.proposal_out.parent.mkdir(parents=True, exist_ok=True)
        args.proposal_out.write_text(json.dumps(proposal, indent=2) + "\n", encoding="utf-8")
        print(f"calibration proposal written: {args.proposal_out}; quality_pass={proposal['proposal_quality_pass']}")
        return 0 if proposal["proposal_quality_pass"] else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
