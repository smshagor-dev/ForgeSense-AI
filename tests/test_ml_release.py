from __future__ import annotations

import hashlib

from forgesense_ml.release import build_reference_dataset, evaluate_reference_model


def test_reference_dataset_is_reproducible_and_hashed() -> None:
    commit = "1" * 40
    first, manifest_a = build_reference_dataset(repository_commit=commit)
    second, manifest_b = build_reference_dataset(repository_commit=commit)
    assert first == second
    assert manifest_a == manifest_b
    assert manifest_a["dataset_sha256"] == hashlib.sha256(first).hexdigest()
    assert manifest_a["row_count"] > 1000
    assert manifest_a["synthetic"] is True


def test_reference_evaluation_records_virtual_boundaries() -> None:
    report = evaluate_reference_model()
    assert report["schema"] == "forgesense.ml_evaluation.v1"
    assert report["virtual_only"] is True
    assert report["summary"]["all_validation_scenarios_passed"] is True
    assert report["summary"]["normal_false_terminal_actions"] == 0
    assert report["selection"]["compact_neural_baseline_status"] == "not_promoted"
    assert any("synthetic" in item.lower() for item in report["limitations"])
