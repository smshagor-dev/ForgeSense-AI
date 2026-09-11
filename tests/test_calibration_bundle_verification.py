from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.prepare_calibration_change_package import (
    CalibrationChangePackageError,
    build_change_package,
    publish_change_package,
)
from tools.verify_calibration_bundle import (
    CalibrationBundleVerificationError,
    verify_bundle,
)

COMMIT = "d" * 40


def _json_bytes(data: dict) -> bytes:
    return (json.dumps(data, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _canonical_sha256(data: dict) -> str:
    blob = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fixture(tmp_path: Path, *, review_ready: bool = True) -> tuple[Path, Path, Path]:
    source_root = tmp_path / "source"
    session_dir = source_root / "run-01"
    session_dir.mkdir(parents=True)

    diagnostic = {"synthetic": True, "samples": [1, 2, 3]}
    diagnostic_path = session_dir / "diag.json"
    diagnostic_path.write_bytes(_json_bytes(diagnostic))

    session = {
        "schema": "forgesense.calibration_session.v1",
        "capture_id": "CAP-RUN-01",
        "repository_commit": COMMIT,
    }
    session_path = session_dir / "session.json"
    session_path.write_bytes(_json_bytes(session))

    policy = {"schema": "forgesense.calibration_review_policy.v1", "minimum_runs": 1}
    policy_path = source_root / "policy.json"
    policy_path.write_bytes(_json_bytes(policy))

    campaign_manifest = {
        "schema": "forgesense.calibration_campaign_manifest.v1",
        "campaign_id": "CAMPAIGN-VERIFY-001",
        "repository_commit": COMMIT,
        "review_policy": "policy.json",
        "runs": [{"run_id": "run-01", "session_manifest": "run-01/session.json"}],
    }
    campaign_manifest_path = source_root / "campaign-manifest.json"
    campaign_manifest_path.write_bytes(_json_bytes(campaign_manifest))

    capture = {
        "schema": "forgesense.calibration_capture.v1",
        "capture_id": "CAP-RUN-01",
        "repository_commit": COMMIT,
        "authority": {
            "assembled_from_read_only_diagnostics": True,
            "independent_reference_values_required": True,
            "automatic_runtime_application": False,
            "may_relax_hard_safety_limits": False,
        },
        "evidence": [
            {
                "file": "diag.json",
                "sha256": _sha256(diagnostic_path.read_bytes()),
                "description": "synthetic diagnostic evidence",
            }
        ],
    }
    capture_bytes = _json_bytes(capture)

    proposal = {
        "schema": "forgesense.calibration_proposal.v1",
        "source_capture_id": capture["capture_id"],
        "source_capture_sha256": _canonical_sha256(capture),
        "repository_commit": COMMIT,
        "proposal_quality_pass": review_ready,
        "authority": {
            "review_required": True,
            "automatic_runtime_application": False,
            "may_relax_hard_safety_limits": False,
        },
    }
    proposal_bytes = _json_bytes(proposal)

    review = {
        "schema": "forgesense.calibration_review.v1",
        "review_ready": review_ready,
        "source_capture_ids": [capture["capture_id"]],
        "source_proposal_sha256": [_canonical_sha256(proposal)],
        "authority": {
            "reviewer_approval_required": True,
            "source_control_change_required": True,
            "automatic_runtime_application": False,
            "may_relax_hard_safety_limits": False,
        },
        "provenance": {
            "run_count": 1,
            "minimum_runs": 1,
        },
        "current": {
            "mean_slope_ma_per_count_candidate": 0.0005,
            "mean_intercept_ma_candidate": 1.0,
            "engineering_uncertainty_proxy_ma_k2": 12.0,
            "repeatability_pass": review_ready,
        },
        "temperature": {
            "mean_offset_c_candidate": 0.2,
            "engineering_uncertainty_proxy_c_k2": 0.15,
            "repeatability_pass": review_ready,
        },
        "accelerometer": {
            "mean_bias_mg_candidate": {"x": 10.0, "y": -5.0, "z": 8.0},
            "engineering_uncertainty_proxy_mg_k2": 15.0,
            "repeatability_pass": review_ready,
        },
        "checks": {"proposal_quality_pass": review_ready},
    }
    review_bytes = _json_bytes(review)

    campaign = {
        "schema": "forgesense.calibration_campaign.v1",
        "campaign_id": campaign_manifest["campaign_id"],
        "repository_commit": COMMIT,
        "authority": {
            "review_only": True,
            "reviewer_approval_required": True,
            "source_control_change_required": True,
            "automatic_runtime_application": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
        "run_count": 1,
        "minimum_runs": 1,
        "runs": [
            {
                "run_id": "run-01",
                "source_session_manifest": "run-01/session.json",
                "capture_artifact": "runs/run-01/capture.json",
                "proposal_artifact": "runs/run-01/proposal.json",
                "capture_sha256": _sha256(capture_bytes),
                "proposal_sha256": _sha256(proposal_bytes),
                "proposal_quality_pass": review_ready,
                "source_capture_id": capture["capture_id"],
            }
        ],
        "review_artifact": "review.json",
        "review_sha256": _sha256(review_bytes),
        "review_ready": review_ready,
    }
    campaign_bytes = _json_bytes(campaign)

    bundle = tmp_path / "bundle"
    (bundle / "runs/run-01").mkdir(parents=True)
    files = {
        "campaign.json": campaign_bytes,
        "review.json": review_bytes,
        "runs/run-01/capture.json": capture_bytes,
        "runs/run-01/proposal.json": proposal_bytes,
    }
    for relative, content in files.items():
        target = bundle / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    index_core = {
        "schema": "forgesense.calibration_evidence_index.v1",
        "campaign_id": campaign["campaign_id"],
        "repository_commit": COMMIT,
        "source_entries": [
            {
                "role": "campaign_manifest",
                "path": "<campaign-manifest-content>",
                "sha256": _canonical_sha256(campaign_manifest),
                "hash_mode": "canonical_json",
            },
            {
                "role": "review_policy",
                "path": "policy.json",
                "sha256": _sha256(policy_path.read_bytes()),
                "hash_mode": "raw_file_bytes",
            },
            {
                "role": "session_manifest",
                "run_id": "run-01",
                "path": "run-01/session.json",
                "sha256": _sha256(session_path.read_bytes()),
                "hash_mode": "raw_file_bytes",
            },
        ],
        "generated_entries": [
            {
                "role": "generated_artifact",
                "path": relative,
                "sha256": _sha256(content),
                "hash_mode": "generated_file_bytes",
            }
            for relative, content in sorted(files.items())
        ],
        "authority": {
            "integrity_index_only": True,
            "digital_signature_present": False,
            "automatic_runtime_application": False,
            "may_relax_hard_safety_limits": False,
        },
    }
    evidence_index = dict(index_core)
    evidence_index["integrity_seal"] = {
        "algorithm": "sha256",
        "root_sha256": _canonical_sha256(index_core),
        "covers": "canonical JSON of evidence-index fields excluding integrity_seal",
        "digital_signature_present": False,
    }
    (bundle / "evidence-index.json").write_bytes(_json_bytes(evidence_index))
    return bundle, source_root, campaign_manifest_path


def test_bundle_integrity_can_be_verified_without_source_files(tmp_path: Path) -> None:
    bundle, _, _ = _fixture(tmp_path)
    result = verify_bundle(bundle)
    assert result["bundle_integrity_pass"] is True
    assert result["semantic_chain_pass"] is True
    assert result["source_provenance_pass"] is False
    assert result["review_ready"] is True


def test_full_source_provenance_verifies_session_policy_and_diagnostic_files(tmp_path: Path) -> None:
    bundle, source_root, campaign_manifest = _fixture(tmp_path)
    result = verify_bundle(bundle, source_root=source_root, campaign_manifest=campaign_manifest)
    assert result["source_provenance_pass"] is True
    assert result["source_items_verified"] == 4


def test_generated_artifact_tamper_is_rejected(tmp_path: Path) -> None:
    bundle, _, _ = _fixture(tmp_path)
    capture = bundle / "runs/run-01/capture.json"
    capture.write_text(capture.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(CalibrationBundleVerificationError, match="generated artifact hash mismatch"):
        verify_bundle(bundle)


def test_evidence_root_tamper_is_rejected(tmp_path: Path) -> None:
    bundle, _, _ = _fixture(tmp_path)
    index_path = bundle / "evidence-index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["campaign_id"] = "TAMPERED"
    index_path.write_bytes(_json_bytes(index))
    with pytest.raises(CalibrationBundleVerificationError, match="root SHA-256 mismatch"):
        verify_bundle(bundle)


def test_original_diagnostic_tamper_is_rejected_by_source_provenance(tmp_path: Path) -> None:
    bundle, source_root, campaign_manifest = _fixture(tmp_path)
    (source_root / "run-01/diag.json").write_text('{"tampered": true}\n', encoding="utf-8")
    with pytest.raises(CalibrationBundleVerificationError, match="diagnostic evidence hash mismatch"):
        verify_bundle(bundle, source_root=source_root, campaign_manifest=campaign_manifest)


def test_change_package_requires_review_ready_campaign(tmp_path: Path) -> None:
    bundle, source_root, campaign_manifest = _fixture(tmp_path, review_ready=False)
    with pytest.raises(CalibrationChangePackageError, match="not review-ready"):
        build_change_package(bundle, source_root=source_root, campaign_manifest=campaign_manifest)


def test_reviewer_ready_package_has_no_runtime_write_and_external_signing_request(tmp_path: Path) -> None:
    bundle, source_root, campaign_manifest = _fixture(tmp_path)
    package, signing = build_change_package(bundle, source_root=source_root, campaign_manifest=campaign_manifest)
    assert package["schema"] == "forgesense.calibration_change_package.v1"
    assert package["source_provenance_verified"] is True
    assert package["authority"]["runtime_write_permitted"] is False
    assert package["authority"]["automatic_runtime_application"] is False
    assert package["authority"]["may_control_actuators"] is False
    assert signing["schema"] == "forgesense.calibration_signing_request.v1"
    assert signing["external_signature_required"] is True
    assert signing["digital_signature_present"] is False
    assert hashlib.sha256(signing["signing_payload"].encode("utf-8")).hexdigest() == signing["payload_sha256"]


def test_change_package_publication_is_atomic_and_never_overwrites(tmp_path: Path) -> None:
    bundle, source_root, campaign_manifest = _fixture(tmp_path)
    out_dir = tmp_path / "change-package"
    publish_change_package(
        bundle,
        source_root=source_root,
        campaign_manifest=campaign_manifest,
        out_dir=out_dir,
    )
    assert (out_dir / "change-package.json").is_file()
    assert (out_dir / "signing-request.json").is_file()
    assert (out_dir / "signing-payload.txt").is_file()
    with pytest.raises(CalibrationChangePackageError, match="already exists"):
        publish_change_package(
            bundle,
            source_root=source_root,
            campaign_manifest=campaign_manifest,
            out_dir=out_dir,
        )
