from __future__ import annotations

from dataclasses import asdict
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from forgesense_sim.scenarios import build_scenario, run_scenario
from forgesense_sim.validation import run_validation_matrix

from .baseline import HealthClass
from .reference import fit_reference_model
from .runtime import EdgeInferenceRuntime

DATASET_SCHEMA = "forgesense.ml_dataset.v1"
EVALUATION_SCHEMA = "forgesense.ml_evaluation.v1"
SCENARIOS = (
    "normal",
    "bearing_degradation",
    "overcurrent",
    "cooling_loss",
    "sensor_dropout",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_reference_dataset(*, repository_commit: str) -> tuple[bytes, dict[str, Any]]:
    if len(repository_commit) != 40 or any(ch not in "0123456789abcdef" for ch in repository_commit.lower()):
        raise ValueError("repository_commit must be a full 40-hex SHA")
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "scenario",
            "sample_index",
            "time_s",
            "temperature_c",
            "vibration_rms_g",
            "current_a",
            "valid_temperature",
            "valid_vibration",
            "valid_current",
            "fault_active",
        ]
    )
    scenario_meta: list[dict[str, Any]] = []
    row_count = 0
    for name in SCENARIOS:
        scenario = build_scenario(name)
        snapshots = run_scenario(scenario)
        scenario_meta.append(
            {
                "name": name,
                "seed": scenario.seed,
                "samples": scenario.samples,
                "dt_s": scenario.dt_s,
                "fault_start": scenario.fault_start,
                "fault_kind": scenario.fault_kind,
            }
        )
        for snapshot in snapshots:
            fault_active = scenario.fault_start is not None and snapshot.sample_index >= scenario.fault_start
            writer.writerow(
                [
                    name,
                    snapshot.sample_index,
                    f"{snapshot.time_s:.6f}",
                    f"{snapshot.temperature_c:.9f}",
                    f"{snapshot.vibration_rms_g:.9f}",
                    f"{snapshot.current_a:.9f}",
                    int(snapshot.valid_temperature),
                    int(snapshot.valid_vibration),
                    int(snapshot.valid_current),
                    int(fault_active),
                ]
            )
            row_count += 1
    csv_bytes = output.getvalue().encode("utf-8")
    manifest = {
        "schema": DATASET_SCHEMA,
        "dataset_id": "forgesense-synthetic-reference-v1",
        "synthetic": True,
        "repository_commit": repository_commit.lower(),
        "feature_schema_version": 1,
        "row_count": row_count,
        "dataset_sha256": _sha256_bytes(csv_bytes),
        "scenarios": scenario_meta,
        "split_policy": "scenario/time-aware; adjacent windows from one run are not randomly split",
        "physical_evidence": False,
    }
    return csv_bytes, manifest


def evaluate_reference_model() -> dict[str, Any]:
    model = fit_reference_model()
    matrix = run_validation_matrix()
    results = [
        {
            **asdict(item),
            "terminal_state": item.terminal_state.name if item.terminal_state is not None else None,
        }
        for item in matrix
    ]
    normal = next(item for item in matrix if item.scenario == "normal")
    fault_results = [item for item in matrix if item.scenario not in {"normal", "sensor_dropout", "link_loss", "emergency"}]
    deterministic_fault_detection = sum(1 for item in fault_results if item.passed)

    # Evaluate the normal reference trace after warm-up directly to report
    # warning/critical inference incidence independently from controller state.
    runtime = EdgeInferenceRuntime(model, window_size=8)
    warnings = 0
    critical = 0
    observations = 0
    for snapshot in run_scenario(build_scenario("normal")):
        observation = runtime.ingest(snapshot)
        if observation is None:
            continue
        observations += 1
        warnings += int(int(observation.health_class) == int(HealthClass.WARNING))
        critical += int(int(observation.health_class) == int(HealthClass.CRITICAL))

    return {
        "schema": EVALUATION_SCHEMA,
        "model": model.to_dict(),
        "virtual_only": True,
        "matrix": results,
        "summary": {
            "normal_false_terminal_actions": 0 if normal.passed else 1,
            "normal_inference_observations": observations,
            "normal_warning_observations": warnings,
            "normal_critical_observations": critical,
            "declared_fault_scenarios_detected": deterministic_fault_detection,
            "declared_fault_scenarios_total": len(fault_results),
            "all_validation_scenarios_passed": all(item.passed for item in matrix),
        },
        "selection": {
            "selected_model_family": "diagonal_gaussian_anomaly_baseline",
            "compact_neural_baseline_status": "not_promoted",
            "rationale": (
                "A neural model is not justified by synthetic-only evidence. The smallest auditable baseline remains selected "
                "until representative physical data demonstrate a measurable benefit under grouped/time-aware evaluation."
            ),
        },
        "limitations": [
            "synthetic data only",
            "not a physical false-alarm rate",
            "not a missed-fault probability",
            "not a production accuracy or certification claim",
        ],
    }


def write_release_artifacts(output_dir: Path, *, repository_commit: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_bytes, manifest = build_reference_dataset(repository_commit=repository_commit)
    (output_dir / "reference-dataset.csv").write_bytes(csv_bytes)
    (output_dir / "reference-dataset-manifest.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "reference-model-evaluation.json").write_text(
        json.dumps(evaluate_reference_model(), indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
