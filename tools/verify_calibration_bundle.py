from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

EVIDENCE_INDEX_SCHEMA = "forgesense.calibration_evidence_index.v1"
CAMPAIGN_SCHEMA = "forgesense.calibration_campaign.v1"
REVIEW_SCHEMA = "forgesense.calibration_review.v1"
CAPTURE_SCHEMA = "forgesense.calibration_capture.v1"
PROPOSAL_SCHEMA = "forgesense.calibration_proposal.v1"
VERIFICATION_SCHEMA = "forgesense.calibration_bundle_verification.v1"
HEX40 = re.compile(r"^[0-9a-fA-F]{40}$")
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


class CalibrationBundleVerificationError(ValueError):
    pass


def _canonical_sha256(data: dict) -> str:
    blob = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError as exc:
        raise CalibrationBundleVerificationError(f"required file not found: {path}") from exc
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CalibrationBundleVerificationError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CalibrationBundleVerificationError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise CalibrationBundleVerificationError(f"{label} must contain a JSON object: {path}")
    return data


def _require_hash(value: object, label: str) -> str:
    text = str(value or "")
    if not HEX64.fullmatch(text):
        raise CalibrationBundleVerificationError(f"{label} must be a 64-hex SHA-256")
    return text.lower()


def _safe_bundle_path(value: object, label: str) -> PurePosixPath:
    text = str(value or "").replace("\\", "/")
    path = PurePosixPath(text)
    if not text or path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise CalibrationBundleVerificationError(f"{label} is not a safe relative bundle path")
    return path


def _strict_authority(mapping: object, expected: dict[str, bool], label: str) -> None:
    if not isinstance(mapping, dict):
        raise CalibrationBundleVerificationError(f"{label} authority is missing")
    for key, value in expected.items():
        if mapping.get(key) is not value:
            raise CalibrationBundleVerificationError(f"{label} authority field {key} is invalid")


def _verify_generated_entries(bundle_dir: Path, index: dict) -> list[str]:
    entries = index.get("generated_entries")
    if not isinstance(entries, list) or not entries:
        raise CalibrationBundleVerificationError("evidence index has no generated_entries")

    seen: set[PurePosixPath] = set()
    verified: list[str] = []
    for item_index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise CalibrationBundleVerificationError(f"generated_entries[{item_index}] must be an object")
        relative = _safe_bundle_path(entry.get("path"), f"generated_entries[{item_index}].path")
        if relative in seen:
            raise CalibrationBundleVerificationError(f"duplicate generated artifact {relative}")
        seen.add(relative)
        expected = _require_hash(entry.get("sha256"), f"generated_entries[{item_index}].sha256")
        actual = _file_sha256(bundle_dir.joinpath(*relative.parts))
        if actual != expected:
            raise CalibrationBundleVerificationError(f"generated artifact hash mismatch: {relative}")
        verified.append(str(relative))

    actual_files = {
        path.relative_to(bundle_dir).as_posix()
        for path in bundle_dir.rglob("*")
        if path.is_file() and path.name != "evidence-index.json"
    }
    expected_files = {str(path) for path in seen}
    extras = sorted(actual_files - expected_files)
    missing = sorted(expected_files - actual_files)
    if extras:
        raise CalibrationBundleVerificationError(f"bundle contains unindexed generated files: {extras}")
    if missing:
        raise CalibrationBundleVerificationError(f"bundle is missing indexed generated files: {missing}")
    return verified


def _verify_semantic_chain(bundle_dir: Path, index: dict) -> tuple[dict, dict, list[dict]]:
    campaign = _load_json(bundle_dir / "campaign.json", "campaign artifact")
    review = _load_json(bundle_dir / "review.json", "review artifact")
    if campaign.get("schema") != CAMPAIGN_SCHEMA:
        raise CalibrationBundleVerificationError("campaign artifact has unsupported schema")
    if review.get("schema") != REVIEW_SCHEMA:
        raise CalibrationBundleVerificationError("review artifact has unsupported schema")

    if campaign.get("campaign_id") != index.get("campaign_id"):
        raise CalibrationBundleVerificationError("campaign_id differs between campaign and evidence index")
    repository_commit = str(campaign.get("repository_commit", "")).lower()
    if not HEX40.fullmatch(repository_commit):
        raise CalibrationBundleVerificationError("campaign repository_commit must be a full 40-hex SHA")
    if repository_commit != str(index.get("repository_commit", "")).lower():
        raise CalibrationBundleVerificationError("repository_commit differs between campaign and evidence index")

    _strict_authority(
        campaign.get("authority"),
        {
            "review_only": True,
            "reviewer_approval_required": True,
            "source_control_change_required": True,
            "automatic_runtime_application": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
        "campaign",
    )
    _strict_authority(
        review.get("authority"),
        {
            "reviewer_approval_required": True,
            "source_control_change_required": True,
            "automatic_runtime_application": False,
            "may_relax_hard_safety_limits": False,
        },
        "review",
    )

    review_hash = _require_hash(campaign.get("review_sha256"), "campaign.review_sha256")
    if _file_sha256(bundle_dir / "review.json") != review_hash:
        raise CalibrationBundleVerificationError("campaign review hash does not match review.json")
    if bool(campaign.get("review_ready")) is not bool(review.get("review_ready")):
        raise CalibrationBundleVerificationError("campaign and review disagree on review_ready")

    runs = campaign.get("runs")
    if not isinstance(runs, list) or not runs:
        raise CalibrationBundleVerificationError("campaign contains no runs")
    if int(campaign.get("run_count", -1)) != len(runs):
        raise CalibrationBundleVerificationError("campaign run_count is inconsistent")

    run_reports: list[dict] = []
    for run_index, run in enumerate(runs):
        if not isinstance(run, dict):
            raise CalibrationBundleVerificationError(f"campaign.runs[{run_index}] must be an object")
        capture_rel = _safe_bundle_path(run.get("capture_artifact"), f"campaign.runs[{run_index}].capture_artifact")
        proposal_rel = _safe_bundle_path(run.get("proposal_artifact"), f"campaign.runs[{run_index}].proposal_artifact")
        capture_path = bundle_dir.joinpath(*capture_rel.parts)
        proposal_path = bundle_dir.joinpath(*proposal_rel.parts)
        if _file_sha256(capture_path) != _require_hash(run.get("capture_sha256"), f"campaign.runs[{run_index}].capture_sha256"):
            raise CalibrationBundleVerificationError(f"capture hash mismatch for run {run.get('run_id')}")
        if _file_sha256(proposal_path) != _require_hash(run.get("proposal_sha256"), f"campaign.runs[{run_index}].proposal_sha256"):
            raise CalibrationBundleVerificationError(f"proposal hash mismatch for run {run.get('run_id')}")

        capture = _load_json(capture_path, f"capture for run {run.get('run_id')}")
        proposal = _load_json(proposal_path, f"proposal for run {run.get('run_id')}")
        if capture.get("schema") != CAPTURE_SCHEMA:
            raise CalibrationBundleVerificationError(f"capture schema is invalid for run {run.get('run_id')}")
        if proposal.get("schema") != PROPOSAL_SCHEMA:
            raise CalibrationBundleVerificationError(f"proposal schema is invalid for run {run.get('run_id')}")
        _strict_authority(
            capture.get("authority"),
            {
                "assembled_from_read_only_diagnostics": True,
                "independent_reference_values_required": True,
                "automatic_runtime_application": False,
                "may_relax_hard_safety_limits": False,
            },
            f"capture {run.get('run_id')}",
        )
        _strict_authority(
            proposal.get("authority"),
            {
                "review_required": True,
                "automatic_runtime_application": False,
                "may_relax_hard_safety_limits": False,
            },
            f"proposal {run.get('run_id')}",
        )
        if str(capture.get("repository_commit", "")).lower() != repository_commit:
            raise CalibrationBundleVerificationError(f"capture repository commit mismatch for run {run.get('run_id')}")
        if str(proposal.get("repository_commit", "")).lower() != repository_commit:
            raise CalibrationBundleVerificationError(f"proposal repository commit mismatch for run {run.get('run_id')}")
        if proposal.get("source_capture_id") != capture.get("capture_id"):
            raise CalibrationBundleVerificationError(f"proposal/capture identifier mismatch for run {run.get('run_id')}")
        source_capture_hash = _require_hash(proposal.get("source_capture_sha256"), f"proposal {run.get('run_id')}.source_capture_sha256")
        if _canonical_sha256(capture) != source_capture_hash:
            raise CalibrationBundleVerificationError(f"proposal source capture hash mismatch for run {run.get('run_id')}")
        evidence = capture.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise CalibrationBundleVerificationError(f"capture evidence is missing for run {run.get('run_id')}")
        for evidence_index, evidence_entry in enumerate(evidence):
            if not isinstance(evidence_entry, dict):
                raise CalibrationBundleVerificationError(f"capture evidence entry is invalid for run {run.get('run_id')}")
            _require_hash(evidence_entry.get("sha256"), f"capture {run.get('run_id')}.evidence[{evidence_index}].sha256")
        run_reports.append({
            "run_id": str(run.get("run_id", "")),
            "capture_artifact": str(capture_rel),
            "proposal_artifact": str(proposal_rel),
            "source_session_manifest": str(run.get("source_session_manifest", "")),
            "diagnostic_evidence_files": len(evidence),
            "proposal_quality_pass": proposal.get("proposal_quality_pass") is True,
        })
    return campaign, review, run_reports


def _verify_source_provenance(bundle_dir: Path, index: dict, campaign: dict, source_root: Path, campaign_manifest: Path) -> dict:
    source_root = source_root.resolve()
    campaign_manifest = campaign_manifest.resolve()
    entries = index.get("source_entries")
    if not isinstance(entries, list) or not entries:
        raise CalibrationBundleVerificationError("evidence index has no source_entries")

    campaign_manifest_data = _load_json(campaign_manifest, "campaign manifest")
    verified_sources = 0
    for entry_index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise CalibrationBundleVerificationError(f"source_entries[{entry_index}] must be an object")
        role = str(entry.get("role", ""))
        expected = _require_hash(entry.get("sha256"), f"source_entries[{entry_index}].sha256")
        if role == "campaign_manifest":
            if entry.get("hash_mode") != "canonical_json":
                raise CalibrationBundleVerificationError("campaign manifest must use canonical_json hash mode")
            actual = _canonical_sha256(campaign_manifest_data)
        else:
            relative = _safe_bundle_path(entry.get("path"), f"source_entries[{entry_index}].path")
            source_path = source_root.joinpath(*relative.parts)
            if entry.get("hash_mode") != "raw_file_bytes":
                raise CalibrationBundleVerificationError(f"source entry {relative} has unsupported hash mode")
            actual = _file_sha256(source_path)
        if actual != expected:
            raise CalibrationBundleVerificationError(f"source provenance hash mismatch for {role}")
        verified_sources += 1

    for run_index, run in enumerate(campaign.get("runs", [])):
        session_rel = _safe_bundle_path(run.get("source_session_manifest"), f"campaign.runs[{run_index}].source_session_manifest")
        session_dir = source_root.joinpath(*session_rel.parts).parent
        capture_rel = _safe_bundle_path(run.get("capture_artifact"), f"campaign.runs[{run_index}].capture_artifact")
        capture = _load_json(bundle_dir.joinpath(*capture_rel.parts), f"capture for run {run.get('run_id')}")
        for evidence_index, evidence in enumerate(capture.get("evidence", [])):
            relative = _safe_bundle_path(evidence.get("file"), f"capture {run.get('run_id')}.evidence[{evidence_index}].file")
            expected = _require_hash(evidence.get("sha256"), f"capture {run.get('run_id')}.evidence[{evidence_index}].sha256")
            actual = _file_sha256(session_dir.joinpath(*relative.parts))
            if actual != expected:
                raise CalibrationBundleVerificationError(f"diagnostic evidence hash mismatch for run {run.get('run_id')}: {relative}")
            verified_sources += 1

    if str(campaign_manifest_data.get("repository_commit", "")).lower() != str(campaign.get("repository_commit", "")).lower():
        raise CalibrationBundleVerificationError("campaign manifest repository_commit differs from packaged campaign")
    if campaign_manifest_data.get("campaign_id") != campaign.get("campaign_id"):
        raise CalibrationBundleVerificationError("campaign manifest campaign_id differs from packaged campaign")
    return {"source_provenance_verified": True, "verified_source_items": verified_sources}


def verify_bundle(bundle_dir: Path, *, source_root: Path | None = None, campaign_manifest: Path | None = None) -> dict:
    bundle_dir = bundle_dir.resolve()
    index = _load_json(bundle_dir / "evidence-index.json", "evidence index")
    if index.get("schema") != EVIDENCE_INDEX_SCHEMA:
        raise CalibrationBundleVerificationError("unsupported evidence index schema")
    _strict_authority(
        index.get("authority"),
        {
            "integrity_index_only": True,
            "digital_signature_present": False,
            "automatic_runtime_application": False,
            "may_relax_hard_safety_limits": False,
        },
        "evidence index",
    )
    seal = index.get("integrity_seal")
    if not isinstance(seal, dict) or seal.get("algorithm") != "sha256":
        raise CalibrationBundleVerificationError("evidence index integrity seal must use sha256")
    if seal.get("digital_signature_present") is not False:
        raise CalibrationBundleVerificationError("evidence index must not claim a digital signature")
    claimed_root = _require_hash(seal.get("root_sha256"), "integrity_seal.root_sha256")
    index_core = {key: value for key, value in index.items() if key != "integrity_seal"}
    actual_root = _canonical_sha256(index_core)
    if claimed_root != actual_root:
        raise CalibrationBundleVerificationError("evidence index root SHA-256 mismatch")

    generated = _verify_generated_entries(bundle_dir, index)
    campaign, review, run_reports = _verify_semantic_chain(bundle_dir, index)

    source_status = {"source_provenance_verified": False, "verified_source_items": 0}
    if (source_root is None) != (campaign_manifest is None):
        raise CalibrationBundleVerificationError("source_root and campaign_manifest must be supplied together")
    if source_root is not None and campaign_manifest is not None:
        source_status = _verify_source_provenance(bundle_dir, index, campaign, source_root, campaign_manifest)

    return {
        "schema": VERIFICATION_SCHEMA,
        "campaign_id": campaign["campaign_id"],
        "repository_commit": campaign["repository_commit"],
        "bundle_integrity_pass": True,
        "semantic_chain_pass": True,
        "source_provenance_pass": source_status["source_provenance_verified"],
        "review_ready": review.get("review_ready") is True,
        "evidence_root_sha256": claimed_root,
        "generated_artifacts_verified": len(generated),
        "source_items_verified": source_status["verified_source_items"],
        "runs": run_reports,
        "authority": {
            "verification_only": True,
            "automatic_runtime_application": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ForgeSense calibration campaign bundle integrity and provenance")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--campaign-manifest", type=Path)
    parser.add_argument("--report-out", type=Path)
    args = parser.parse_args()
    try:
        result = verify_bundle(
            args.bundle,
            source_root=args.source_root,
            campaign_manifest=args.campaign_manifest,
        )
    except CalibrationBundleVerificationError as exc:
        raise SystemExit(f"calibration bundle verification failed: {exc}") from exc
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        "calibration bundle verification PASS: "
        f"bundle_integrity={result['bundle_integrity_pass']} "
        f"source_provenance={result['source_provenance_pass']} "
        f"review_ready={result['review_ready']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
