from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    tool = (root / "tools/run_calibration_campaign.py").read_text(encoding="utf-8")
    template = (root / "hardware/calibration/calibration_campaign_template_v1.json").read_text(encoding="utf-8")
    tests = (root / "tests/test_calibration_campaign.py").read_text(encoding="utf-8")
    docs = (root / "docs/CALIBRATION_CAMPAIGN.md").read_text(encoding="utf-8")

    for token in (
        'CAMPAIGN_SCHEMA = "forgesense.calibration_campaign_manifest.v1"',
        'CAMPAIGN_RESULT_SCHEMA = "forgesense.calibration_campaign.v1"',
        'EVIDENCE_INDEX_SCHEMA = "forgesense.calibration_evidence_index.v1"',
        '"review_only": True',
        '"automatic_runtime_application": False',
        '"may_control_actuators": False',
        '"may_relax_hard_safety_limits": False',
        '"digital_signature_present": False',
        '"integrity_index_only": True',
        'build_proposal(capture)',
        'review_proposals(proposals, policy)',
        'tempfile.mkdtemp',
        'staging.rename(out_dir)',
    ):
        assert token in tool, token

    for forbidden in (
        "serial.serial",
        "uart_rx",
        "load_enable_o",
        "flash_calibration",
        "apply_runtime_calibration",
        "write_fpga",
        "set_hard_limit",
        "update_safety_limit",
    ):
        assert forbidden not in tool.lower(), forbidden

    for token in (
        '"schema": "forgesense.calibration_campaign_manifest.v1"',
        '"repository_commit"',
        '"review_policy"',
        '"run_id"',
        '"session_manifest"',
    ):
        assert token in template, token

    for token in (
        "test_campaign_builds_three_run_review_and_integrity_index",
        "test_policy_minimum_runs_is_enforced_before_bundle_generation",
        "test_campaign_rejects_session_commit_mismatch",
        "test_campaign_rejects_duplicate_session_manifest",
        "test_failed_campaign_does_not_publish_partial_output",
        "test_existing_output_directory_is_never_overwritten",
    ):
        assert token in tests, token

    assert "atomic" in docs.lower()
    assert "sha-256" in docs.lower()
    assert "not a digital signature" in docs.lower()
    assert "three" in docs.lower()
    assert "does not apply calibration" in docs.lower()

    print(
        "calibration_campaign_check PASS: repeated-run orchestration, atomic publication, evidence integrity and review-only authority are present"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
