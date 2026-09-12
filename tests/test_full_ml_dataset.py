from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from forgesense_ml.full_dataset import (
    DATASET_ID,
    SCENARIOS,
    WINDOW_SIZE,
    generate_full_dataset,
)


COMMIT = "1" * 40


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _run_ids(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["run_id"] for row in csv.DictReader(handle)}


def test_full_dataset_is_deterministic_and_leakage_safe(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    manifest_a = generate_full_dataset(
        first,
        repository_commit=COMMIT,
        runs_per_scenario=3,
        sample_limit=24,
    )
    manifest_b = generate_full_dataset(
        second,
        repository_commit=COMMIT,
        runs_per_scenario=3,
        sample_limit=24,
    )

    assert manifest_a["dataset_id"] == DATASET_ID
    assert manifest_a["scenario_count"] == len(SCENARIOS)
    assert manifest_a["window_size"] == WINDOW_SIZE
    assert manifest_a["raw_rows"] == manifest_b["raw_rows"]
    assert manifest_a["window_rows"] == manifest_b["window_rows"]

    for filename in (
        "raw-train.csv",
        "raw-validation.csv",
        "raw-test.csv",
        "windows-train.csv",
        "windows-validation.csv",
        "windows-test.csv",
        "baseline-normal-train.csv",
        "scenario-summary.csv",
        "manifest.json",
        "README.md",
        "checksums.sha256",
    ):
        assert _sha256(first / filename) == _sha256(second / filename), filename

    train_runs = _run_ids(first / "raw-train.csv")
    validation_runs = _run_ids(first / "raw-validation.csv")
    test_runs = _run_ids(first / "raw-test.csv")
    assert train_runs
    assert validation_runs
    assert test_runs
    assert train_runs.isdisjoint(validation_runs)
    assert train_runs.isdisjoint(test_runs)
    assert validation_runs.isdisjoint(test_runs)


def test_full_dataset_contains_truth_measurements_labels_and_windows(tmp_path: Path) -> None:
    output = tmp_path / "dataset"
    manifest = generate_full_dataset(
        output,
        repository_commit=COMMIT,
        runs_per_scenario=3,
        sample_limit=28,
    )

    with (output / "raw-train.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    required = {
        "true_temperature_c",
        "true_vibration_rms_g",
        "true_current_a",
        "temperature_c",
        "vibration_rms_g",
        "current_a",
        "valid_temperature",
        "valid_vibration",
        "valid_current",
        "fault_severity",
        "target_anomaly",
        "target_health_class",
    }
    assert required.issubset(rows[0])
    assert {row["target_health_class"] for row in rows}.issubset({"0", "1", "2"})

    with (output / "windows-train.csv").open("r", encoding="utf-8", newline="") as handle:
        window_rows = list(csv.DictReader(handle))
    assert window_rows
    assert "temperature_std" in window_rows[0]
    assert "vibration_delta" in window_rows[0]
    assert "current_mean" in window_rows[0]
    assert "valid_vibration_fraction" in window_rows[0]

    assert manifest["physical_evidence"] is False
    assert manifest["authority"]["may_replace_physical_validation"] is False
    assert manifest["baseline_normal_train_rows"] > 0


def test_manifest_hashes_match_generated_files(tmp_path: Path) -> None:
    output = tmp_path / "dataset"
    generate_full_dataset(
        output,
        repository_commit=COMMIT,
        runs_per_scenario=3,
        sample_limit=24,
    )
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    for filename, meta in manifest["files"].items():
        path = output / filename
        assert path.exists()
        assert path.stat().st_size == meta["bytes"]
        assert _sha256(path) == meta["sha256"]
