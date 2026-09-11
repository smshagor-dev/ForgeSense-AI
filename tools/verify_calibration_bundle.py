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


def _safe_relative_path(value: object, label: str) -> PurePosixPath:
    text = str(value or "").replace("\\", "/")
    path = PurePosixPath(text)
    if not text or path.is_absolute() or ".." in path.parts or "." in path.parts or any(":" in part for part in path.parts):
        raise CalibrationBundleVerificationError(f"{label} is not a safe relative path")
    return path


def _confined_path(root: Path, relative: PurePosixPath, label: str) -> Path:
    root = root.resolve()
    target = root.joinpath(*relative.parts)
    try:
        target.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise CalibrationBundleVerificationError(f"{label} escapes its allowed root") from exc
    probe = root
    for part in relative.parts:
        probe = probe / part
        if probe.is_symlink():
            raise CalibrationBundleVerificationError(f"{label} traverses a symbolic link")
    return target


def _resolve_manifest_reference(base_dir: Path, value: object, label: str) -> Path:
    text = str(value or "").strip()
    if not text:
        raise CalibrationBundleVerificationError(f"{label} is required")
    path = Path(text)
    return path.resolve() if path.is_absolute() else (base_dir / path).resolve()


def _require_beneath(path: Path, root: Path, label: str) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise CalibrationBundleVerificationError(f"{label} is outside source_root") from exc


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

    for path in bundle_dir.rglob("*"):
        if path.is_symlink():
            raise CalibrationBundleVerificationError(f"bundle contains symbolic link: {path.relative_to(bundle_dir)}")

    seen: set[PurePosixPath] = set()
    verified: list[str] = []
    for item_index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise CalibrationBundleVerificationError(f"generated_entries[{item_index}] must be an object")
        if entry.get("role") != "generated_artifact" or entry.get("hash_mode") != "generated_file_bytes":
            raise CalibrationBundleVerificationError(f"generated_entries[{item_index}] has invalid role/hash mode")
        relative = _safe_relative_path(entry.get("path"), f"generated_entries[{item_index}].path")
        if relative in seen:
            raise CalibrationBundleVerificationError(f"duplicate generated artifact {relative}")
        seen.add(relative)
        target = _confined_path(bundle_dir, relative, f"generated artifact {relative}")
        expected = _require_hash(entry.get("sha256"), f"generated_entries[{item_index}].sha256")
        actual = _file_sha256(target)
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
    if int(campaign.get("minimum_runs", 0)) < 1:
        raise CalibrationBundleVerificationError("campaign minimum_runs is invalid")

    run_reports: list[dict] = []
    capture_ids: list[str] = []
    proposal_hashes: list[str] = []
    for run_index, run in enumerate(runs):
        if not isinstance(run, dict):
            raise CalibrationBundleVerificationError(f"campaign.runs[{run_index}] must be an object")
        capture_rel = _safe_relative_path(run.get("capture_artifact"), f"campaign.runs[{run_index}].capture_artifact")
        proposal_rel = _safe_relative_path(run.get("proposal_artifact"), f"campaign.runs[{run_index}].proposal_artifact")
        capture_path = _confined_path(bundle_dir, capture_rel, f"capture artifact for run {run.get('run_id')}")
        proposal_path = _confined_path(bundle_dir, proposal_rel, f"proposal artifact for run {run.get('run_id')}")
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
        capture_id = str(capture.get("capture_id", ""))
        if proposal.get("source_capture_id") != capture_id:
            raise CalibrationBundleVerificationError(f"proposal/capture identifier mismatch for run {run.get('run_id')}")
        if run.get("source_capture_id") != capture_id:
            raise CalibrationBundleVerificationError(f"campaign/capture identifier mismatch for run {run.get('run_id')}")
        if bool(run.get("proposal_quality_pass")) is not bool(proposal.get("proposal_quality_pass")):
            raise CalibrationBundleVerificationError(f"campaign/proposal quality verdict mismatch for run {run.get('run_id')}")
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
        capture_ids.append(capture_id)
        proposal_hashes.append(_canonical_sha256(proposal))
        run_reports.append(
            {
                "run_id": str(run.get("run_id", "")),
                "capture_artifact": str(capture_rel),
                "proposal_artifact": str(proposal_rel),
                "source_session_manifest": str(run.get("source_session_manifest", "")),
                "diagnostic_evidence_files": len(evidence),
                "proposal_quality_pass": proposal.get("proposal_quality_pass") is True,
            }
        )

    if review.get("source_capture_ids") != capture_ids:
        raise CalibrationBundleVerificationError("review source_capture_ids do not match campaign captures")
    if review.get("source_proposal_sha256") != proposal_hashes:
        raise CalibrationBundleVerificationError("review source_proposal_sha256 does not match generated proposals")
    provenance = review.get("provenance")
    if not isinstance(provenance, dict) or int(provenance.get("run_count", -1)) != len(runs):
        raise CalibrationBundleVerificationError("review provenance run_count is inconsistent")
    if int(provenance.get("minimum_runs", -1)) != int(campaign.get("minimum_runs", -2)):
        raise CalibrationBundleVerificationError("campaign/review minimum_runs are inconsistent")
    return campaign, review, run_reports


def _verify_source_provenance(
    bundle_dir: Path,
    index: dict,
    campaign: dict,
    source_root: Path,
    campaign_manifest: Path,
) -> dict:
    source_root = source_root.resolve()
    campaign_manifest = campaign_manifest.resolve()
    _require_beneath(campaign_manifest, source_root, "campaign_manifest")
    entries = index.get("source_entries")
    if not isinstance(entries, list) or not entries:
        raise CalibrationBundleVerificationError("evidence index has no source_entries")

    allowed_roles = {"campaign_manifest", "review_policy", "session_manifest"}
    for entry_index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise CalibrationBundleVerificationError(f"source_entries[{entry_index}] must be an object")
        if entry.get("role") not in allowed_roles:
            raise CalibrationBundleVerificationError(f"source_entries[{entry_index}] has unsupported role")
    campaign_entries = [entry for entry in entries if entry.get("role") == "campaign_manifest"]
    policy_entries = [entry for entry in entries if entry.get("role") == "review_policy"]
    session_entries = [entry for entry in entries if entry.get("role") == "session_manifest"]
    if len(campaign_entries) != 1 or len(policy_entries) != 1:
        raise CalibrationBundleVerificationError("source index must contain exactly one campaign manifest and one review policy")
    if len(session_entries) != len(campaign.get("runs", [])):
        raise CalibrationBundleVerificationError("source index session-manifest count does not match campaign runs")

    campaign_manifest_data = _load_json(campaign_manifest, "campaign manifest")
    campaign_entry = campaign_entries[0]
    if campaign_entry.get("hash_mode") != "canonical_json":
        raise CalibrationBundleVerificationError("campaign manifest must use canonical_json hash mode")
    if _canonical_sha256(campaign_manifest_data) != _require_hash(campaign_entry.get("sha256"), "campaign manifest sha256"):
        raise CalibrationBundleVerificationError("source provenance hash mismatch for campaign_manifest")

    if str(campaign_manifest_data.get("repository_commit", "")).lower() != str(campaign.get("repository_commit", "")).lower():
        raise CalibrationBundleVerificationError("campaign manifest repository_commit differs from packaged campaign")
    if campaign_manifest_data.get("campaign_id") != campaign.get("campaign_id"):
        raise CalibrationBundleVerificationError("campaign manifest campaign_id differs from packaged campaign")

    policy_path = _resolve_manifest_reference(
        campaign_manifest.parent,
        campaign_manifest_data.get("review_policy"),
        "campaign_manifest.review_policy",
    )
    policy_entry = policy_entries[0]
    if policy_entry.get("hash_mode") != "raw_file_bytes":
        raise CalibrationBundleVerificationError("review policy must use raw_file_bytes hash mode")
    if _file_sha256(policy_path) != _require_hash(policy_entry.get("sha256"), "review policy sha256"):
        raise CalibrationBundleVerificationError("source provenance hash mismatch for review_policy")

    manifest_runs = campaign_manifest_data.get("runs")
    packaged_runs = campaign.get("runs")
    if not isinstance(manifest_runs, list) or not isinstance(packaged_runs, list):
        raise CalibrationBundleVerificationError("campaign manifest/package runs are invalid")
    manifest_by_id = {str(run.get("run_id", "")): run for run in manifest_runs if isinstance(run, dict)}
    packaged_by_id = {str(run.get("run_id", "")): run for run in packaged_runs if isinstance(run, dict)}
    if set(manifest_by_id) != set(packaged_by_id) or len(manifest_by_id) != len(manifest_runs):
        raise CalibrationBundleVerificationError("campaign manifest run IDs differ from packaged campaign")
    session_entry_by_id = {str(entry.get("run_id", "")): entry for entry in session_entries}
    if set(session_entry_by_id) != set(packaged_by_id) or len(session_entry_by_id) != len(session_entries):
        raise CalibrationBundleVerificationError("source session run IDs differ from packaged campaign")

    verified_sources = 2
    for run_id in packaged_by_id:
        manifest_run = manifest_by_id[run_id]
        packaged_run = packaged_by_id[run_id]
        session_path = _resolve_manifest_reference(
            campaign_manifest.parent,
            manifest_run.get("session_manifest"),
            f"campaign manifest session for {run_id}",
        )
        _require_beneath(session_path, source_root, f"session manifest for {run_id}")
        session_entry = session_entry_by_id[run_id]
        if session_entry.get("hash_mode") != "raw_file_bytes":
            raise CalibrationBundleVerificationError(f"session manifest for {run_id} must use raw_file_bytes hash mode")
        if _file_sha256(session_path) != _require_hash(session_entry.get("sha256"), f"session manifest {run_id} sha256"):
            raise CalibrationBundleVerificationError(f"source provenance hash mismatch for session_manifest {run_id}")
        verified_sources += 1

        capture_rel = _safe_relative_path(packaged_run.get("capture_artifact"), f"campaign run {run_id}.capture_artifact")
        capture_path = _confined_path(bundle_dir, capture_rel, f"capture artifact for {run_id}")
        capture = _load_json(capture_path, f"capture for run {run_id}")
        for evidence_index, evidence in enumerate(capture.get("evidence", [])):
            relative = _safe_relative_path(evidence.get("file"), f"capture {run_id}.evidence[{evidence_index}].file")
            diagnostic_path = session_path.parent.joinpath(*relative.parts).resolve()
            _require_beneath(diagnostic_path, source_root, f"diagnostic evidence for {run_id}")
            expected = _require_hash(evidence.get("sha256"), f"capture {run_id}.evidence[{evidence_index}].sha256")
            if _file_sha256(diagnostic_path) != expected:
                raise CalibrationBundleVerificationError(f"diagnostic evidence hash mismatch for run {run_id}: {relative}")
            verified_sources += 1

    return {"source_provenance_verified": True, "verified_source_items": verified_sources}


def verify_bundle(
    bundle_dir: Path,
    *,
    source_root: Path | None = None,
    campaign_manifest: Path | None = None,
) -> dict:
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
        source_status = _verify_source_provenance(
            bundle_dir,
            index,
            campaign,
            source_root,
            campaign_manifest,
        )

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
