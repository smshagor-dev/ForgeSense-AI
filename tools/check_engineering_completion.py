from __future__ import annotations

import json
from pathlib import Path

SCHEMA = "forgesense.repository_engineering_completion.v1"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "engineering/completion_manifest_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest.get("schema") == SCHEMA
    assert manifest.get("scope_id") == "FORGESENSE-V1-REPOSITORY"

    repository_scope = manifest.get("repository_scope")
    external = manifest.get("external_evidence_gates")
    authority = manifest.get("authority")
    assert isinstance(repository_scope, list) and repository_scope
    assert isinstance(external, list) and external
    assert isinstance(authority, dict)

    ids: set[str] = set()
    for item in repository_scope:
        assert isinstance(item, dict)
        item_id = item.get("id")
        assert isinstance(item_id, str) and item_id and item_id not in ids
        ids.add(item_id)
        assert item.get("status") == "complete", f"repository item not complete: {item_id}"
        evidence = item.get("evidence")
        assert isinstance(evidence, list) and evidence, f"repository item lacks evidence: {item_id}"
        for relative in evidence:
            assert isinstance(relative, str) and relative
            path = root / relative
            assert path.exists(), f"completion evidence missing: {relative}"

    external_ids: set[str] = set()
    for item in external:
        assert isinstance(item, dict)
        item_id = item.get("id")
        assert isinstance(item_id, str) and item_id and item_id not in external_ids
        external_ids.add(item_id)
        assert item.get("external_evidence_required") is True
        assert item_id not in ids

    assert authority.get("repository_completion_is_not_physical_validation") is True
    assert authority.get("repository_completion_is_not_certification") is True
    assert authority.get("may_relax_hard_safety_limits") is False

    makefile = (root / "Makefile").read_text(encoding="utf-8")
    for target in (
        "software-qualification-check:",
        "ml-release-check:",
        "release-security-check:",
        "engineering-complete-check:",
    ):
        assert target in makefile, f"missing Makefile completion target: {target}"

    implementation_workflow = (root / ".github/workflows/implementation.yml").read_text(encoding="utf-8")
    assert "make engineering-complete-check" in implementation_workflow

    production_app = (root / "firmware/esp32/main/app_main.cpp").read_text(encoding="utf-8")
    transparent_bridge = (root / "firmware/esp32_commissioning/main/app_main.cpp").read_text(encoding="utf-8")
    for forbidden in (
        "CALIBRATION-WRITE",
        "PrepareRecord",
        "CommitRecord",
        "RotateAuthorityKey",
        "set_hard_limit",
        "update_safety_limit",
    ):
        assert forbidden not in production_app
        assert forbidden not in transparent_bridge

    threat = (root / "docs/THREAT_MODEL.md").read_text(encoding="utf-8")
    hazard = (root / "docs/HAZARD_ANALYSIS.md").read_text(encoding="utf-8")
    status = (root / "docs/IMPLEMENTATION_STATUS.md").read_text(encoding="utf-8")
    completion = (root / "docs/ENGINEERING_COMPLETION.md").read_text(encoding="utf-8")
    roadmap = (root / "ROADMAP.md").read_text(encoding="utf-8")
    for token in ("private signing keys", "audit-ledger", "Secure Boot"):
        assert token.lower() in threat.lower()
    for token in ("overcurrent", "emergency stop", "calibration"):
        assert token.lower() in hazard.lower()
    assert "100% repository engineering implementation" in completion
    assert "repository implementation: complete" in status.lower()
    assert "repository engineering implementation — complete" in roadmap.lower()

    print(
        f"engineering_completion_check PASS: {len(repository_scope)} repository deliverables complete; "
        f"{len(external)} external evidence gates explicitly separated"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
