from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

try:
    from tools.assemble_calibration_capture import CalibrationAssemblyError, assemble_capture
    from tools.capture_calibration import build_proposal
    from tools.review_calibration import review_proposals
except ModuleNotFoundError:  # Direct execution from repository root.
    from assemble_calibration_capture import CalibrationAssemblyError, assemble_capture
    from capture_calibration import build_proposal
    from review_calibration import review_proposals

CAMPAIGN_SCHEMA = "forgesense.calibration_campaign_manifest.v1"
CAMPAIGN_RESULT_SCHEMA = "forgesense.calibration_campaign.v1"
EVIDENCE_INDEX_SCHEMA = "forgesense.calibration_evidence_index.v1"
HEX40 = re.compile(r"^[0-9a-fA-F]{40}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class CalibrationCampaignError(ValueError):
    pass


def _json_bytes(data: dict) -> bytes:
    return (json.dumps(data, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _canonical_sha256(data: dict) -> str:
    blob = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _bytes_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError as exc:
        raise CalibrationCampaignError(f"required file not found: {path}") from exc
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CalibrationCampaignError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CalibrationCampaignError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise CalibrationCampaignError(f"{label} must contain a JSON object: {path}")
    return data


def _resolve(base_dir: Path, value: object, label: str) -> Path:
    text = str(value or "").strip()
    if not text:
        raise CalibrationCampaignError(f"{label} is required")
    path = Path(text)
    return path if path.is_absolute() else base_dir / path


def _display_path(path: Path, base_dir: Path) -> str:
    try:
        return str(path.relative_to(base_dir))
    except ValueError:
        return str(path)


def _validate_campaign(manifest: dict) -> None:
    if manifest.get("schema") != CAMPAIGN_SCHEMA:
        raise CalibrationCampaignError("unsupported calibration campaign schema")
    campaign_id = str(manifest.get("campaign_id", "")).strip()
    if not SAFE_ID.fullmatch(campaign_id):
        raise CalibrationCampaignError("campaign_id must be 1-64 safe filename characters")
    commit = str(manifest.get("repository_commit", ""))
    if not HEX40.fullmatch(commit):
        raise CalibrationCampaignError("repository_commit must be a full 40-hex SHA")
    if not str(manifest.get("review_policy", "")).strip():
        raise CalibrationCampaignError("review_policy is required")

    runs = manifest.get("runs")
    if not isinstance(runs, list) or len(runs) < 2:
        raise CalibrationCampaignError("campaign requires at least two runs")

    run_ids: set[str] = set()
    session_paths: set[str] = set()
    for index, run in enumerate(runs):
        if not isinstance(run, dict):
            raise CalibrationCampaignError(f"runs[{index}] must be an object")
        run_id = str(run.get("run_id", "")).strip()
        if not SAFE_ID.fullmatch(run_id):
            raise CalibrationCampaignError(f"runs[{index}].run_id is invalid")
        if run_id in run_ids:
            raise CalibrationCampaignError(f"duplicate run_id {run_id!r}")
        run_ids.add(run_id)
        session = str(run.get("session_manifest", "")).strip()
        if not session:
            raise CalibrationCampaignError(f"runs[{index}].session_manifest is required")
        if session in session_paths:
            raise CalibrationCampaignError(f"session manifest {session!r} is reused by more than one campaign run")
        session_paths.add(session)

    boards = manifest.get("boards")
    if boards is not None:
        if not isinstance(boards, dict):
            raise CalibrationCampaignError("boards must be an object when provided")
        for key in ("fpga_revision", "esp32_revision", "sensor_board_revision"):
            if not str(boards.get(key, "")).strip():
                raise CalibrationCampaignError(f"boards.{key} is required when campaign boards are declared")


def _validate_session_scope(campaign: dict, session: dict, path: Path) -> None:
    expected_commit = str(campaign["repository_commit"]).lower()
    session_commit = str(session.get("repository_commit", "")).lower()
    if session_commit != expected_commit:
        raise CalibrationCampaignError(
            f"{path}: session repository_commit does not match campaign repository_commit"
        )
    expected_boards = campaign.get("boards")
    if expected_boards is not None and session.get("boards") != expected_boards:
        raise CalibrationCampaignError(f"{path}: session board revisions do not match campaign boards")


def _validate_policy_minimum(policy: dict, run_count: int) -> int:
    try:
        minimum_runs = int(policy.get("minimum_runs", 0))
    except (TypeError, ValueError) as exc:
        raise CalibrationCampaignError("review policy minimum_runs is invalid") from exc
    if minimum_runs < 2:
        raise CalibrationCampaignError("review policy minimum_runs must be at least 2")
    if run_count < minimum_runs:
        raise CalibrationCampaignError(
            f"campaign contains {run_count} runs but review policy requires at least {minimum_runs}"
        )
    return minimum_runs


def build_campaign_bundle(manifest: dict, *, base_dir: Path) -> tuple[dict[str, bytes], bool]:
    _validate_campaign(manifest)
    base_dir = base_dir.resolve()
    policy_path = _resolve(base_dir, manifest["review_policy"], "review_policy").resolve()
    policy = _load_json(policy_path, "review policy")
    minimum_runs = _validate_policy_minimum(policy, len(manifest["runs"]))

    generated: dict[str, bytes] = {}
    proposals: list[dict] = []
    run_results: list[dict] = []
    source_entries: list[dict] = [
        {
            "role": "campaign_manifest",
            "path": "<campaign-manifest-content>",
            "sha256": _canonical_sha256(manifest),
            "hash_mode": "canonical_json",
        },
        {
            "role": "review_policy",
            "path": _display_path(policy_path, base_dir),
            "sha256": _file_sha256(policy_path),
            "hash_mode": "raw_file_bytes",
        },
    ]
    resolved_sessions: set[Path] = set()

    for index, run in enumerate(manifest["runs"]):
        run_id = str(run["run_id"])
        session_path = _resolve(base_dir, run["session_manifest"], f"runs[{index}].session_manifest").resolve()
        if session_path in resolved_sessions:
            raise CalibrationCampaignError(
                f"resolved session manifest {session_path} is reused by more than one campaign run"
            )
        resolved_sessions.add(session_path)
        session = _load_json(session_path, f"session manifest for {run_id}")
        _validate_session_scope(manifest, session, session_path)

        try:
            capture = assemble_capture(session, base_dir=session_path.parent)
            proposal = build_proposal(capture)
        except (CalibrationAssemblyError, TypeError, ValueError) as exc:
            raise CalibrationCampaignError(f"run {run_id}: calibration assembly failed: {exc}") from exc

        proposal["source_capture_sha256"] = _canonical_sha256(capture)
        proposals.append(proposal)

        capture_name = f"runs/{run_id}/capture.json"
        proposal_name = f"runs/{run_id}/proposal.json"
        capture_bytes = _json_bytes(capture)
        proposal_bytes = _json_bytes(proposal)
        generated[capture_name] = capture_bytes
        generated[proposal_name] = proposal_bytes

        session_display = _display_path(session_path, base_dir)
        source_entries.append(
            {
                "role": "session_manifest",
                "run_id": run_id,
                "path": session_display,
                "sha256": _file_sha256(session_path),
                "hash_mode": "raw_file_bytes",
            }
        )
        run_results.append(
            {
                "run_id": run_id,
                "source_session_manifest": session_display,
                "capture_artifact": capture_name,
                "proposal_artifact": proposal_name,
                "capture_sha256": _bytes_sha256(capture_bytes),
                "proposal_sha256": _bytes_sha256(proposal_bytes),
                "proposal_quality_pass": proposal.get("proposal_quality_pass") is True,
                "source_capture_id": str(proposal.get("source_capture_id", "")),
            }
        )

    try:
        review = review_proposals(proposals, policy)
    except (TypeError, ValueError) as exc:
        raise CalibrationCampaignError(f"campaign review failed: {exc}") from exc

    review_bytes = _json_bytes(review)
    generated["review.json"] = review_bytes

    campaign_result = {
        "schema": CAMPAIGN_RESULT_SCHEMA,
        "campaign_id": manifest["campaign_id"],
        "repository_commit": str(manifest["repository_commit"]).lower(),
        "authority": {
            "review_only": True,
            "reviewer_approval_required": True,
            "source_control_change_required": True,
            "automatic_runtime_application": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
        "run_count": len(run_results),
        "minimum_runs": minimum_runs,
        "runs": run_results,
        "review_artifact": "review.json",
        "review_sha256": _bytes_sha256(review_bytes),
        "review_ready": review.get("review_ready") is True,
        "note": (
            "Campaign completion packages evidence and repeated-run review only. "
            "It never applies calibration or changes deterministic safety limits."
        ),
    }
    campaign_bytes = _json_bytes(campaign_result)
    generated["campaign.json"] = campaign_bytes

    generated_entries = [
        {
            "role": "generated_artifact",
            "path": path,
            "sha256": _bytes_sha256(content),
            "hash_mode": "generated_file_bytes",
        }
        for path, content in sorted(generated.items())
    ]
    index_core = {
        "schema": EVIDENCE_INDEX_SCHEMA,
        "campaign_id": manifest["campaign_id"],
        "repository_commit": str(manifest["repository_commit"]).lower(),
        "source_entries": source_entries,
        "generated_entries": generated_entries,
        "authority": {
            "integrity_index_only": True,
            "digital_signature_present": False,
            "automatic_runtime_application": False,
            "may_relax_hard_safety_limits": False,
        },
    }
    root_sha256 = _canonical_sha256(index_core)
    evidence_index = dict(index_core)
    evidence_index["integrity_seal"] = {
        "algorithm": "sha256",
        "root_sha256": root_sha256,
        "covers": "canonical JSON of evidence-index fields excluding integrity_seal",
        "digital_signature_present": False,
    }
    generated["evidence-index.json"] = _json_bytes(evidence_index)
    return generated, campaign_result["review_ready"]


def publish_campaign_bundle(manifest: dict, *, base_dir: Path, out_dir: Path) -> bool:
    out_dir = out_dir.resolve()
    if out_dir.exists():
        raise CalibrationCampaignError(f"output directory already exists: {out_dir}")
    bundle, review_ready = build_campaign_bundle(manifest, base_dir=base_dir)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.staging-", dir=out_dir.parent))
    try:
        for relative, content in bundle.items():
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        staging.rename(out_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return review_ready


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an atomic repeated-run ForgeSense calibration campaign evidence bundle"
    )
    parser.add_argument("campaign", type=Path, help="forgesense.calibration_campaign_manifest.v1 JSON")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    try:
        campaign = _load_json(args.campaign, "campaign manifest")
        review_ready = publish_campaign_bundle(
            campaign,
            base_dir=args.campaign.parent,
            out_dir=args.out_dir,
        )
    except CalibrationCampaignError as exc:
        raise SystemExit(f"calibration campaign failed: {exc}") from exc

    print(f"calibration campaign written: {args.out_dir}; review_ready={review_ready}")
    return 0 if review_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
