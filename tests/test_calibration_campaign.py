from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.run_calibration_campaign import (
    CalibrationCampaignError,
    build_campaign_bundle,
    publish_campaign_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "b" * 40
BOARDS = {
    "fpga_revision": "fpga-a",
    "esp32_revision": "esp32-a",
    "sensor_board_revision": "sensor-a",
}


def _canonical_sha256(data: dict) -> str:
    blob = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _write_diagnostic(
    path: Path,
    *,
    ads_raw: int,
    temperature_c: float,
    count: int = 24,
    x_mg: int = 10,
    y_mg: int = -5,
    z_mg: int = 1010,
    capture_pass: bool = True,
) -> None:
    samples = []
    for index in range(count):
        samples.append(
            {
                "sequence": index,
                "timestamp_ms": 1000 + index * 50,
                "ads_ch0_raw": ads_raw + (index % 3) - 1,
                "ads_ch1_raw": 0,
                "tmp117_temperature_c": temperature_c + ((index % 3) - 1) * 0.1,
                "tmp117_temperature_deci_c": round(temperature_c * 10),
                "adxl355_milli_g": {
                    "x": x_mg + (index % 3) - 1,
                    "y": y_mg + (index % 5) - 2,
                    "z": z_mg + (index % 4) - 1,
                },
                "flags": "0x003F",
                "sample_set_complete": True,
                "devices_trusted": True,
                "usable_for_calibration": True,
            }
        )
    result = {
        "schema": "forgesense.calibration_diagnostic_capture.v1",
        "authority": {
            "read_only": True,
            "may_control_actuators": False,
            "may_apply_calibration": False,
            "may_relax_hard_safety_limits": False,
        },
        "capture_pass": capture_pass,
        "frames": count,
        "ignored_frames": 0,
        "usable_samples": count,
        "sequence_gaps": 0,
        "sequence_faults": 0,
        "crc_or_frame_errors": 0,
        "discarded_bytes": 0,
        "latest": samples[-1],
        "samples": samples,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"mode": "calibration", "result": result}, indent=2) + "\n", encoding="utf-8")


def _write_session(base: Path, run_id: str, *, raw_shift: int = 0, temp_shift: float = 0.0) -> Path:
    run_dir = base / run_id
    current_points = []
    for index, (raw, amps) in enumerate(
        ((0, 0.0), (1_000_000, 0.5), (2_000_000, 1.0), (4_000_000, 2.0), (6_400_000, 3.2))
    ):
        diag = run_dir / f"current-{index}.json"
        _write_diagnostic(diag, ads_raw=raw + raw_shift, temperature_c=25.0 + temp_shift)
        current_points.append({"diagnostic_file": diag.name, "reference_current_a": amps})

    temperature_points = []
    for index, reference in enumerate((20.0, 25.0, 30.0)):
        diag = run_dir / f"temp-{index}.json"
        _write_diagnostic(diag, ads_raw=2_000_000 + raw_shift, temperature_c=reference - 0.2 + temp_shift)
        temperature_points.append(
            {"diagnostic_file": diag.name, "reference_temperature_c": reference + temp_shift}
        )

    accel = run_dir / "accel.json"
    _write_diagnostic(accel, ads_raw=0, temperature_c=25.0, count=30)

    session = {
        "schema": "forgesense.calibration_session.v1",
        "capture_id": f"CAP-{run_id}",
        "repository_commit": COMMIT,
        "boards": BOARDS,
        "instruments": [
            {
                "type": "reference_meter",
                "manufacturer_model": "synthetic",
                "asset_or_serial": "test",
                "calibration_status": "synthetic-test-only",
            }
        ],
        "environment": {"ambient_temperature_c": 25.0 + temp_shift},
        "measurement_uncertainty": {
            "reference_current_ma_k2": 10.0,
            "reference_temperature_c_k2": 0.1,
            "reference_accelerometer_mg_k2": 10.0,
        },
        "current": {"points": current_points},
        "temperature": {"points": temperature_points},
        "accelerometer": {
            "expected_stationary_mg": {"x": 0.0, "y": 0.0, "z": 1000.0},
            "diagnostic_files": [accel.name],
        },
    }
    session_path = run_dir / "session.json"
    session_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
    return session_path


def _campaign(tmp_path: Path) -> dict:
    policy_source = ROOT / "hardware/calibration/calibration_review_policy_v1.json"
    policy = tmp_path / "policy.json"
    policy.write_bytes(policy_source.read_bytes())

    sessions = [
        _write_session(tmp_path, "run-01", raw_shift=0, temp_shift=0.00),
        _write_session(tmp_path, "run-02", raw_shift=1000, temp_shift=0.02),
        _write_session(tmp_path, "run-03", raw_shift=-1000, temp_shift=-0.02),
    ]
    return {
        "schema": "forgesense.calibration_campaign_manifest.v1",
        "campaign_id": "CAL-CAMPAIGN-001",
        "repository_commit": COMMIT,
        "boards": BOARDS,
        "review_policy": policy.name,
        "runs": [
            {"run_id": f"run-0{index + 1}", "session_manifest": str(path.relative_to(tmp_path))}
            for index, path in enumerate(sessions)
        ],
    }


def test_campaign_builds_three_run_review_and_integrity_index(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path)
    bundle, review_ready = build_campaign_bundle(campaign, base_dir=tmp_path)

    assert review_ready is True
    assert "campaign.json" in bundle
    assert "review.json" in bundle
    assert "evidence-index.json" in bundle
    for run_id in ("run-01", "run-02", "run-03"):
        assert f"runs/{run_id}/capture.json" in bundle
        assert f"runs/{run_id}/proposal.json" in bundle

    campaign_result = json.loads(bundle["campaign.json"])
    assert campaign_result["review_ready"] is True
    assert campaign_result["run_count"] == 3
    assert campaign_result["authority"]["automatic_runtime_application"] is False
    assert campaign_result["authority"]["may_control_actuators"] is False
    assert campaign_result["runs"][0]["source_session_manifest"] == "run-01/session.json"

    evidence_index = json.loads(bundle["evidence-index.json"])
    assert evidence_index["schema"] == "forgesense.calibration_evidence_index.v1"
    assert evidence_index["integrity_seal"]["algorithm"] == "sha256"
    assert evidence_index["integrity_seal"]["digital_signature_present"] is False
    assert evidence_index["authority"]["integrity_index_only"] is True

    source_roles = [entry["role"] for entry in evidence_index["source_entries"]]
    assert source_roles.count("campaign_manifest") == 1
    assert source_roles.count("review_policy") == 1
    assert source_roles.count("session_manifest") == 3
    review_policy = next(entry for entry in evidence_index["source_entries"] if entry["role"] == "review_policy")
    assert review_policy["path"] == "policy.json"

    generated = {entry["path"]: entry for entry in evidence_index["generated_entries"]}
    assert generated["review.json"]["sha256"] == hashlib.sha256(bundle["review.json"]).hexdigest()
    assert generated["campaign.json"]["sha256"] == hashlib.sha256(bundle["campaign.json"]).hexdigest()

    index_core = {key: value for key, value in evidence_index.items() if key != "integrity_seal"}
    assert evidence_index["integrity_seal"]["root_sha256"] == _canonical_sha256(index_core)


def test_policy_minimum_runs_is_enforced_before_bundle_generation(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path)
    campaign["runs"] = campaign["runs"][:2]
    with pytest.raises(CalibrationCampaignError, match="requires at least 3"):
        build_campaign_bundle(campaign, base_dir=tmp_path)


def test_campaign_rejects_session_commit_mismatch(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path)
    session_path = tmp_path / campaign["runs"][1]["session_manifest"]
    session = json.loads(session_path.read_text(encoding="utf-8"))
    session["repository_commit"] = "c" * 40
    session_path.write_text(json.dumps(session), encoding="utf-8")
    with pytest.raises(CalibrationCampaignError, match="does not match campaign repository_commit"):
        build_campaign_bundle(campaign, base_dir=tmp_path)


def test_campaign_rejects_duplicate_session_manifest(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path)
    campaign["runs"][1]["session_manifest"] = campaign["runs"][0]["session_manifest"]
    with pytest.raises(CalibrationCampaignError, match="reused by more than one campaign run"):
        build_campaign_bundle(campaign, base_dir=tmp_path)


def test_failed_campaign_does_not_publish_partial_output(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path)
    broken_session = tmp_path / campaign["runs"][2]["session_manifest"]
    session = json.loads(broken_session.read_text(encoding="utf-8"))
    broken_diag = broken_session.parent / session["current"]["points"][2]["diagnostic_file"]
    raw = json.loads(broken_diag.read_text(encoding="utf-8"))
    raw["result"]["capture_pass"] = False
    broken_diag.write_text(json.dumps(raw), encoding="utf-8")

    out_dir = tmp_path / "published-campaign"
    with pytest.raises(CalibrationCampaignError, match="calibration assembly failed"):
        publish_campaign_bundle(campaign, base_dir=tmp_path, out_dir=out_dir)
    assert out_dir.exists() is False


def test_existing_output_directory_is_never_overwritten(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path)
    out_dir = tmp_path / "published-campaign"
    out_dir.mkdir()
    marker = out_dir / "keep.txt"
    marker.write_text("retain", encoding="utf-8")

    with pytest.raises(CalibrationCampaignError, match="output directory already exists"):
        publish_campaign_bundle(campaign, base_dir=tmp_path, out_dir=out_dir)
    assert marker.read_text(encoding="utf-8") == "retain"
