from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import fmean, pstdev
from typing import Iterable

from forgesense_sim.plant import (
    ChannelImpairment,
    FaultProfile,
    MachinePlant,
    SensorImpairmentProfile,
)

DATASET_SCHEMA = "forgesense.ml_full_dataset.v2"
DATASET_ID = "forgesense-full-synthetic-v2"
GENERATOR_VERSION = 2
WINDOW_SIZE = 8
DEFAULT_RUNS_PER_SCENARIO = 15

RAW_COLUMNS = (
    "dataset_id",
    "split",
    "scenario",
    "fault_family",
    "run_id",
    "seed",
    "sample_index",
    "time_s",
    "load",
    "speed_rpm",
    "true_temperature_c",
    "true_vibration_rms_g",
    "true_current_a",
    "temperature_c",
    "vibration_rms_g",
    "current_a",
    "valid_temperature",
    "valid_vibration",
    "valid_current",
    "fault_active",
    "fault_severity",
    "target_anomaly",
    "target_health_class",
)

WINDOW_COLUMNS = (
    "dataset_id",
    "split",
    "scenario",
    "fault_family",
    "run_id",
    "seed",
    "window_end_sample",
    "time_s",
    "temperature_mean",
    "temperature_std",
    "temperature_min",
    "temperature_max",
    "temperature_delta",
    "vibration_mean",
    "vibration_std",
    "vibration_min",
    "vibration_max",
    "vibration_delta",
    "current_mean",
    "current_std",
    "current_min",
    "current_max",
    "current_delta",
    "load_mean",
    "speed_rpm_mean",
    "valid_temperature_fraction",
    "valid_vibration_fraction",
    "valid_current_fraction",
    "fault_fraction",
    "target_anomaly",
    "target_health_class",
)


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    family: str
    kind: str
    samples: int = 520
    fault_start_fraction: float = 0.42


SCENARIOS = (
    ScenarioSpec("normal", "normal", "normal"),
    ScenarioSpec("bearing_degradation", "mechanical", "bearing", samples=560),
    ScenarioSpec("overcurrent", "electrical", "overcurrent"),
    ScenarioSpec("cooling_loss", "thermal", "cooling_loss", samples=700),
    ScenarioSpec("bearing_overcurrent", "mixed", "bearing_overcurrent", samples=600),
    ScenarioSpec("cooling_overcurrent", "mixed", "cooling_overcurrent", samples=700),
    ScenarioSpec("temperature_bias", "sensor_integrity", "temperature_bias"),
    ScenarioSpec("vibration_bias", "sensor_integrity", "vibration_bias"),
    ScenarioSpec("current_bias", "sensor_integrity", "current_bias"),
    ScenarioSpec("temperature_drift", "sensor_integrity", "temperature_drift", samples=640),
    ScenarioSpec("vibration_drift", "sensor_integrity", "vibration_drift", samples=640),
    ScenarioSpec("current_drift", "sensor_integrity", "current_drift", samples=640),
    ScenarioSpec("temperature_high_noise", "sensor_integrity", "temperature_high_noise"),
    ScenarioSpec("vibration_high_noise", "sensor_integrity", "vibration_high_noise"),
    ScenarioSpec("current_high_noise", "sensor_integrity", "current_high_noise"),
    ScenarioSpec("temperature_stuck", "sensor_integrity", "temperature_stuck"),
    ScenarioSpec("vibration_stuck", "sensor_integrity", "vibration_stuck"),
    ScenarioSpec("current_stuck", "sensor_integrity", "current_stuck"),
    ScenarioSpec("temperature_saturation", "sensor_integrity", "temperature_saturation"),
    ScenarioSpec("vibration_saturation", "sensor_integrity", "vibration_saturation"),
    ScenarioSpec("current_saturation", "sensor_integrity", "current_saturation"),
    ScenarioSpec("temperature_dropout", "sensor_integrity", "temperature_dropout"),
    ScenarioSpec("vibration_dropout", "sensor_integrity", "vibration_dropout"),
    ScenarioSpec("current_dropout", "sensor_integrity", "current_dropout"),
    ScenarioSpec("multi_sensor_dropout", "sensor_integrity", "multi_sensor_dropout"),
    ScenarioSpec("bearing_sensor_drift", "mixed", "bearing_sensor_drift", samples=640),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _split_for_run(run_index: int, runs_per_scenario: int) -> str:
    if runs_per_scenario < 3:
        raise ValueError("runs_per_scenario must be at least 3")
    train_count = max(1, int(runs_per_scenario * 0.67))
    validation_count = max(1, int(runs_per_scenario * 0.16))
    if train_count + validation_count >= runs_per_scenario:
        validation_count = 1
        train_count = runs_per_scenario - 2
    if run_index < train_count:
        return "train"
    if run_index < train_count + validation_count:
        return "validation"
    return "test"


def _load_profile(index: int, seed: int) -> float:
    levels = (0.34, 0.50, 0.68, 0.78, 0.60)
    level = levels[(index // 55 + seed) % len(levels)]
    ripple = 0.035 * math.sin((index + seed * 3) / 13.0)
    return min(max(level + ripple, 0.15), 0.92)


def _fault_start(samples: int, seed: int, fraction: float) -> int:
    nominal = int(samples * fraction)
    jitter = (seed % 19) - 9
    return min(max(nominal + jitter, WINDOW_SIZE + 8), samples - 12)


def _severity(index: int, start: int, samples: int) -> float:
    if index < start:
        return 0.0
    return min(max((index - start + 1) / max(samples - start, 1), 0.0), 1.0)


def _physical_fault(kind: str, severity: float) -> FaultProfile:
    if kind == "bearing":
        return FaultProfile(bearing=severity)
    if kind == "overcurrent":
        return FaultProfile(overcurrent=min(0.30 + 0.70 * severity, 1.0))
    if kind == "cooling_loss":
        return FaultProfile(cooling_loss=min(0.20 + 0.80 * severity, 1.0))
    if kind == "bearing_overcurrent":
        return FaultProfile(bearing=severity, overcurrent=min(0.25 + 0.75 * severity, 1.0))
    if kind == "cooling_overcurrent":
        return FaultProfile(cooling_loss=min(0.20 + 0.80 * severity, 1.0), overcurrent=min(0.20 + 0.80 * severity, 1.0))
    if kind == "bearing_sensor_drift":
        return FaultProfile(bearing=severity)
    return FaultProfile()


def _impairments(kind: str, severity: float, active: bool) -> SensorImpairmentProfile:
    if not active:
        return SensorImpairmentProfile()
    if kind == "temperature_bias":
        return SensorImpairmentProfile(temperature=ChannelImpairment(bias=1.0 + 8.0 * severity))
    if kind == "vibration_bias":
        return SensorImpairmentProfile(vibration=ChannelImpairment(bias=0.025 + 0.35 * severity))
    if kind == "current_bias":
        return SensorImpairmentProfile(current=ChannelImpairment(bias=0.05 + 0.75 * severity))
    if kind == "temperature_drift":
        return SensorImpairmentProfile(temperature=ChannelImpairment(drift_per_s=0.025 + 0.08 * severity))
    if kind == "vibration_drift":
        return SensorImpairmentProfile(vibration=ChannelImpairment(drift_per_s=0.0007 + 0.0030 * severity))
    if kind == "current_drift":
        return SensorImpairmentProfile(current=ChannelImpairment(drift_per_s=0.0015 + 0.0080 * severity))
    if kind == "temperature_high_noise":
        return SensorImpairmentProfile(temperature=ChannelImpairment(noise_sigma=0.35 + 1.65 * severity))
    if kind == "vibration_high_noise":
        return SensorImpairmentProfile(vibration=ChannelImpairment(noise_sigma=0.020 + 0.120 * severity))
    if kind == "current_high_noise":
        return SensorImpairmentProfile(current=ChannelImpairment(noise_sigma=0.040 + 0.260 * severity))
    if kind == "temperature_stuck":
        return SensorImpairmentProfile(temperature=ChannelImpairment(stuck_value=48.0))
    if kind == "vibration_stuck":
        return SensorImpairmentProfile(vibration=ChannelImpairment(stuck_value=0.19))
    if kind == "current_stuck":
        return SensorImpairmentProfile(current=ChannelImpairment(stuck_value=1.35))
    if kind == "temperature_saturation":
        return SensorImpairmentProfile(temperature=ChannelImpairment(saturation_max=28.0))
    if kind == "vibration_saturation":
        return SensorImpairmentProfile(vibration=ChannelImpairment(saturation_max=0.12))
    if kind == "current_saturation":
        return SensorImpairmentProfile(current=ChannelImpairment(saturation_max=1.15))
    if kind == "temperature_dropout":
        return SensorImpairmentProfile(temperature=ChannelImpairment(dropout=True))
    if kind == "vibration_dropout":
        return SensorImpairmentProfile(vibration=ChannelImpairment(dropout=True))
    if kind == "current_dropout":
        return SensorImpairmentProfile(current=ChannelImpairment(dropout=True))
    if kind == "multi_sensor_dropout":
        return SensorImpairmentProfile(
            temperature=ChannelImpairment(dropout=True),
            vibration=ChannelImpairment(dropout=True),
        )
    if kind == "bearing_sensor_drift":
        return SensorImpairmentProfile(vibration=ChannelImpairment(drift_per_s=0.0010 + 0.0025 * severity))
    return SensorImpairmentProfile()


def _health_class(kind: str, active: bool, severity: float) -> int:
    if not active:
        return 0
    if "dropout" in kind or "stuck" in kind or "saturation" in kind:
        return 2
    return 2 if severity >= 0.70 else 1


def _fmt(value: float) -> str:
    return f"{value:.9f}"


def _window_stats(values: Iterable[float]) -> tuple[float, float, float, float, float]:
    series = list(values)
    mean = fmean(series)
    std = pstdev(series) if len(series) > 1 else 0.0
    return mean, std, min(series), max(series), series[-1] - series[0]


def _window_row(rows: list[dict[str, object]]) -> dict[str, object]:
    last = rows[-1]
    temperature = [float(row["temperature_c"]) for row in rows]
    vibration = [float(row["vibration_rms_g"]) for row in rows]
    current = [float(row["current_a"]) for row in rows]
    t = _window_stats(temperature)
    v = _window_stats(vibration)
    c = _window_stats(current)
    return {
        "dataset_id": DATASET_ID,
        "split": last["split"],
        "scenario": last["scenario"],
        "fault_family": last["fault_family"],
        "run_id": last["run_id"],
        "seed": last["seed"],
        "window_end_sample": last["sample_index"],
        "time_s": last["time_s"],
        "temperature_mean": _fmt(t[0]),
        "temperature_std": _fmt(t[1]),
        "temperature_min": _fmt(t[2]),
        "temperature_max": _fmt(t[3]),
        "temperature_delta": _fmt(t[4]),
        "vibration_mean": _fmt(v[0]),
        "vibration_std": _fmt(v[1]),
        "vibration_min": _fmt(v[2]),
        "vibration_max": _fmt(v[3]),
        "vibration_delta": _fmt(v[4]),
        "current_mean": _fmt(c[0]),
        "current_std": _fmt(c[1]),
        "current_min": _fmt(c[2]),
        "current_max": _fmt(c[3]),
        "current_delta": _fmt(c[4]),
        "load_mean": _fmt(fmean(float(row["load"]) for row in rows)),
        "speed_rpm_mean": _fmt(fmean(float(row["speed_rpm"]) for row in rows)),
        "valid_temperature_fraction": _fmt(fmean(int(row["valid_temperature"]) for row in rows)),
        "valid_vibration_fraction": _fmt(fmean(int(row["valid_vibration"]) for row in rows)),
        "valid_current_fraction": _fmt(fmean(int(row["valid_current"]) for row in rows)),
        "fault_fraction": _fmt(fmean(int(row["fault_active"]) for row in rows)),
        "target_anomaly": max(int(row["target_anomaly"]) for row in rows),
        "target_health_class": max(int(row["target_health_class"]) for row in rows),
    }


def generate_full_dataset(
    output_dir: Path,
    *,
    repository_commit: str,
    runs_per_scenario: int = DEFAULT_RUNS_PER_SCENARIO,
    sample_limit: int | None = None,
) -> dict[str, object]:
    if len(repository_commit) != 40 or any(ch not in "0123456789abcdef" for ch in repository_commit.lower()):
        raise ValueError("repository_commit must be a full 40-hex SHA")
    if runs_per_scenario < 3:
        raise ValueError("runs_per_scenario must be at least 3")
    if sample_limit is not None and sample_limit < WINDOW_SIZE + 8:
        raise ValueError("sample_limit is too small for window generation")

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)

    raw_files = {split: output_dir / f"raw-{split}.csv" for split in ("train", "validation", "test")}
    window_files = {split: output_dir / f"windows-{split}.csv" for split in ("train", "validation", "test")}
    baseline_path = output_dir / "baseline-normal-train.csv"

    raw_handles = {split: path.open("w", encoding="utf-8", newline="") for split, path in raw_files.items()}
    window_handles = {split: path.open("w", encoding="utf-8", newline="") for split, path in window_files.items()}
    baseline_handle = baseline_path.open("w", encoding="utf-8", newline="")
    raw_writers = {split: csv.DictWriter(handle, fieldnames=RAW_COLUMNS, lineterminator="\n") for split, handle in raw_handles.items()}
    window_writers = {split: csv.DictWriter(handle, fieldnames=WINDOW_COLUMNS, lineterminator="\n") for split, handle in window_handles.items()}
    baseline_writer = csv.writer(baseline_handle, lineterminator="\n")
    for writer in raw_writers.values():
        writer.writeheader()
    for writer in window_writers.values():
        writer.writeheader()
    baseline_writer.writerow(("temperature_c", "vibration_rms_g", "current_a", "run_id", "sample_index"))

    split_counts: Counter[str] = Counter()
    window_split_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    scenario_counts: Counter[str] = Counter()
    run_counts: Counter[str] = Counter()
    baseline_rows = 0

    try:
        for scenario_index, spec in enumerate(SCENARIOS):
            for run_index in range(runs_per_scenario):
                split = _split_for_run(run_index, runs_per_scenario)
                seed = 1009 + scenario_index * 1000 + run_index * 37
                samples = min(spec.samples, sample_limit) if sample_limit is not None else spec.samples
                start = _fault_start(samples, seed, spec.fault_start_fraction) if spec.kind != "normal" else samples + 1
                ambient_c = 20.0 + (seed % 9) * 0.75
                plant = MachinePlant(ambient_c=ambient_c, seed=seed)
                run_id = f"{spec.name}-r{run_index:02d}-s{seed}"
                window: deque[dict[str, object]] = deque(maxlen=WINDOW_SIZE)
                run_counts[split] += 1

                for index in range(samples):
                    load = _load_profile(index, seed)
                    severity = _severity(index, start, samples)
                    active = spec.kind != "normal" and index >= start
                    physical_fault = _physical_fault(spec.kind, severity)
                    sample = plant.step(load=load, dt_s=0.1, fault=physical_fault)
                    measured = plant.sense(sample, impairments=_impairments(spec.kind, severity, active))
                    health = _health_class(spec.kind, active, severity)
                    row: dict[str, object] = {
                        "dataset_id": DATASET_ID,
                        "split": split,
                        "scenario": spec.name,
                        "fault_family": spec.family,
                        "run_id": run_id,
                        "seed": seed,
                        "sample_index": index,
                        "time_s": _fmt(sample.time_s),
                        "load": _fmt(sample.load),
                        "speed_rpm": _fmt(sample.speed_rpm),
                        "true_temperature_c": _fmt(sample.temperature_c),
                        "true_vibration_rms_g": _fmt(sample.vibration_rms_g),
                        "true_current_a": _fmt(sample.current_a),
                        "temperature_c": _fmt(measured.temperature_c),
                        "vibration_rms_g": _fmt(measured.vibration_rms_g),
                        "current_a": _fmt(measured.current_a),
                        "valid_temperature": int(measured.valid_temperature),
                        "valid_vibration": int(measured.valid_vibration),
                        "valid_current": int(measured.valid_current),
                        "fault_active": int(active),
                        "fault_severity": _fmt(severity),
                        "target_anomaly": int(active),
                        "target_health_class": health,
                    }
                    raw_writers[split].writerow(row)
                    split_counts[split] += 1
                    scenario_counts[spec.name] += 1
                    class_counts[f"{split}:{health}"] += 1
                    window.append(row)

                    if spec.kind == "normal" and split == "train" and index >= 80 and measured.all_valid:
                        baseline_writer.writerow((_fmt(measured.temperature_c), _fmt(measured.vibration_rms_g), _fmt(measured.current_a), run_id, index))
                        baseline_rows += 1

                    if len(window) == WINDOW_SIZE:
                        window_writers[split].writerow(_window_row(list(window)))
                        window_split_counts[split] += 1
    finally:
        for handle in raw_handles.values():
            handle.close()
        for handle in window_handles.values():
            handle.close()
        baseline_handle.close()

    summary_path = output_dir / "scenario-summary.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("scenario", "family", "raw_rows"))
        for spec in SCENARIOS:
            writer.writerow((spec.name, spec.family, scenario_counts[spec.name]))

    generated_files = [*raw_files.values(), *window_files.values(), baseline_path, summary_path]
    file_meta = {
        path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
        for path in generated_files
    }

    manifest: dict[str, object] = {
        "schema": DATASET_SCHEMA,
        "dataset_id": DATASET_ID,
        "generator_version": GENERATOR_VERSION,
        "repository_commit": repository_commit.lower(),
        "synthetic": True,
        "physical_evidence": False,
        "runs_per_scenario": runs_per_scenario,
        "scenario_count": len(SCENARIOS),
        "total_runs": len(SCENARIOS) * runs_per_scenario,
        "window_size": WINDOW_SIZE,
        "split_policy": "run-grouped deterministic split; no run_id appears in more than one split",
        "raw_rows": dict(split_counts),
        "window_rows": dict(window_split_counts),
        "run_counts": dict(run_counts),
        "baseline_normal_train_rows": baseline_rows,
        "health_class_counts": dict(class_counts),
        "health_classes": {"0": "normal", "1": "warning", "2": "critical"},
        "scenarios": [
            {"name": spec.name, "family": spec.family, "kind": spec.kind, "samples": min(spec.samples, sample_limit) if sample_limit is not None else spec.samples}
            for spec in SCENARIOS
        ],
        "raw_columns": list(RAW_COLUMNS),
        "window_columns": list(WINDOW_COLUMNS),
        "files": file_meta,
        "training_guidance": {
            "current_reference_model": "use baseline-normal-train.csv for the diagonal Gaussian normal-envelope fit",
            "supervised_models": "use windows-train.csv and tune on windows-validation.csv; report final metrics once on windows-test.csv",
            "raw_sequence_models": "use raw-*.csv grouped by run_id; never split adjacent samples from one run across partitions",
        },
        "limitations": [
            "synthetic digital-twin data only",
            "not representative of final physical sensor noise, motor dynamics, EMI, mounting, or environment",
            "not a production false-alarm or missed-fault probability",
            "must be supplemented with retained physical datasets before production model qualification",
        ],
        "authority": {
            "may_change_safety_limits": False,
            "may_control_actuators": False,
            "may_replace_physical_validation": False,
        },
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    readme = f"""# ForgeSense Full Synthetic ML Dataset v2\n\nDataset ID: `{DATASET_ID}`\n\nThis package contains deterministic synthetic training/evaluation data generated from the ForgeSense digital twin. It is not physical machine evidence.\n\n## Files\n\n- `raw-train.csv`, `raw-validation.csv`, `raw-test.csv`: sample-level truth, measured channels, validity, severity and labels.\n- `windows-train.csv`, `windows-validation.csv`, `windows-test.csv`: leakage-safe {WINDOW_SIZE}-sample engineered windows for supervised models.\n- `baseline-normal-train.csv`: clean normal training subset for the current diagonal-Gaussian reference model.\n- `scenario-summary.csv`: scenario/family row counts.\n- `manifest.json`: provenance, split policy, schemas, row counts and hashes.\n- `checksums.sha256`: SHA-256 for every retained artifact.\n\n## Labels\n\n`target_health_class`: `0=normal`, `1=warning`, `2=critical`. `target_anomaly` is binary. Sensor dropout/stuck/saturation cases become critical after fault activation; progressive physical/bias/drift/noise faults transition warning -> critical as severity rises.\n\n## Split rule\n\nSplits are grouped by `run_id`. A run is never divided across train/validation/test, preventing adjacent-window leakage.\n\n## Boundary\n\nThis dataset is synthetic. Final model qualification requires physical data captured from the selected sensors/electronics and representative machinery.\n"""
    readme_path = output_dir / "README.md"
    readme_path.write_text(readme, encoding="utf-8")

    checksum_targets = [*generated_files, manifest_path, readme_path]
    checksum_path = output_dir / "checksums.sha256"
    checksum_path.write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in sorted(checksum_targets, key=lambda item: item.name)),
        encoding="utf-8",
    )

    return manifest
