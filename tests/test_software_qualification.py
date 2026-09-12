from __future__ import annotations

from forgesense_sim.qualification import run_software_qualification


def test_repository_software_qualification_passes() -> None:
    report = run_software_qualification()
    assert report["schema"] == "forgesense.software_qualification.v1"
    assert report["virtual_only"] is True
    assert report["passed"] is True
    assert all(report["checks"].values())
    assert "not a physical soak" in report["evidence_boundary"].lower()
