from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    tool = (root / "tools/review_calibration.py").read_text(encoding="utf-8")
    policy = (root / "hardware/calibration/calibration_review_policy_v1.json").read_text(encoding="utf-8")
    tests = (root / "tests/test_calibration_review.py").read_text(encoding="utf-8")
    docs = (root / "docs/CALIBRATION_REVIEW.md").read_text(encoding="utf-8")

    for token in (
        '"schema": "forgesense.calibration_review.v1"',
        '"reviewer_approval_required": True',
        '"source_control_change_required": True',
        '"automatic_runtime_application": False',
        '"may_relax_hard_safety_limits": False',
        '"measurement_uncertainty_complete"',
        '"accelerometer_stddev_complete"',
        '"slope_span_ppm"',
        '"axis_bias_span_mg"',
        '"review_ready"',
    ):
        assert token in tool, token

    forbidden = (
        "write_fpga",
        "flash_calibration",
        "apply_runtime_calibration",
        "update_safety_limit",
        "set_hard_limit",
    )
    lowered = tool.lower()
    for token in forbidden:
        assert token not in lowered

    for token in (
        '"schema": "forgesense.calibration_review_policy.v1"',
        '"minimum_runs": 3',
        '"require_same_board_revisions": true',
        '"require_same_repository_commit": true',
        '"require_declared": true',
    ):
        assert token in policy, token

    for token in (
        "test_three_consistent_runs_are_review_ready_without_runtime_authority",
        "test_board_revision_mismatch_blocks_review_readiness",
        "test_large_current_gain_drift_is_rejected",
        "test_missing_uncertainty_blocks_review_readiness",
        "test_legacy_proposal_without_axis_stddev_is_not_review_ready",
        "test_authority_tamper_is_rejected",
        "test_too_few_runs_is_not_review_ready",
    ):
        assert token in tests, token

    assert "does not apply calibration" in docs
    assert "does not approve a safety-limit change" in docs
    assert "three" in docs.lower()
    assert "uncertainty" in docs.lower()
    assert "repeatability" in docs.lower()

    print("calibration_review_check PASS: repeatability, uncertainty, evidence completeness and review-only authority gates are present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
