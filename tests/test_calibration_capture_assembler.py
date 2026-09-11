from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.assemble_calibration_capture import CalibrationAssemblyError, assemble_capture
from tools.capture_calibration import build_proposal


def _write_diagnostic(
    path: Path,
    *,
    ads_raw: int,
    temperature_c: float,
    count: int = 24,
    x_mg: int = 10,
    y_mg: int = -5,
    z_mg: int = 1010,
    wrapped: bool = True,
    capture_pass: bool = True,
    sequence_gaps: int = 0,
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
        "sequence_gaps": sequence_gaps,
        "sequence_faults": 0,
        "crc_or_frame_errors": 0,
        "discarded_bytes": 0,
        "latest": samples[-1],
        "samples": samples,
    }
    data = {"mode": "calibration", "result": result} if wrapped else result
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _manifest(tmp_path: Path) -> dict:
    current_files = []
    for index, (raw, amps) in enumerate(
        ((0, 0.0), (1_000_000, 0.5), (2_000_000, 1.0), (4_000_000, 2.0), (6_400_000, 3.2))
    ):
        path = tmp_path / f"current-{index}.json"
        _write_diagnostic(path, ads_raw=raw, temperature_c=25.0, wrapped=index != 0)
        current_files.append({"diagnostic_file": path.name, "reference_current_a": amps})

    temperature_files = []
    for index, reference in enumerate((20.0, 25.0, 30.0)):
        path = tmp_path / f"temp-{index}.json"
        _write_diagnostic(path, ads_raw=2_000_000, temperature_c=reference - 0.2)
        temperature_files.append({"diagnostic_file": path.name, "reference_temperature_c": reference})

    accel_path = tmp_path / "accel.json"
    _write_diagnostic(accel_path, ads_raw=0, temperature_c=25.0, count=30)

    return {
        "schema": "forgesense.calibration_session.v1",
        "capture_id": "CAL-ASSEMBLY-001",
        "repository_commit": "a" * 40,
        "boards": {
            "fpga_revision": "fpga-a",
            "esp32_revision": "esp32-a",
            "sensor_board_revision": "sensor-a",
        },
        "instruments": [
            {
                "type": "reference_meter",
                "manufacturer_model": "synthetic",
                "asset_or_serial": "test",
                "calibration_status": "synthetic-test-only",
            }
        ],
        "environment": {"ambient_temperature_c": 25.0},
        "measurement_uncertainty": {
            "reference_current_ma_k2": 10.0,
            "reference_temperature_c_k2": 0.1,
            "reference_accelerometer_mg_k2": 10.0,
        },
        "current": {"points": current_files},
        "temperature": {"points": temperature_files},
        "accelerometer": {
            "expected_stationary_mg": {"x": 0.0, "y": 0.0, "z": 1000.0},
            "diagnostic_files": [accel_path.name],
        },
    }


def test_assembler_builds_proposal_compatible_capture_from_trusted_diagnostics(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    capture = assemble_capture(manifest, base_dir=tmp_path)

    assert capture["schema"] == "forgesense.calibration_capture.v1"
    assert capture["capture_id"] == "CAL-ASSEMBLY-001"
    assert capture["authority"]["assembled_from_read_only_diagnostics"] is True
    assert capture["authority"]["independent_reference_values_required"] is True
    assert capture["authority"]["automatic_runtime_application"] is False
    assert capture["authority"]["may_relax_hard_safety_limits"] is False
    assert len(capture["current"]["points"]) == 5
    assert len(capture["temperature"]["points"]) == 3
    assert len(capture["accelerometer"]["stationary_samples_mg"]) == 30
    assert capture["current"]["points"][1]["adc_raw"] == pytest.approx(1_000_000.0)
    assert capture["temperature"]["points"][0]["tmp117_temperature_c"] == pytest.approx(19.8)
    assert capture["assembly"]["diagnostic_files"] == 9

    proposal = build_proposal(capture)
    assert proposal["proposal_quality_pass"] is True


def test_evidence_hash_matches_raw_diagnostic_file(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    capture = assemble_capture(manifest, base_dir=tmp_path)
    evidence = {item["file"]: item for item in capture["evidence"]}
    source = tmp_path / "current-0.json"
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    assert evidence["current-0.json"]["sha256"] == expected


def test_failed_or_sequence_broken_diagnostic_is_rejected(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    broken = tmp_path / "current-2.json"
    _write_diagnostic(broken, ads_raw=2_000_000, temperature_c=25.0, capture_pass=False)
    with pytest.raises(CalibrationAssemblyError, match="did not pass"):
        assemble_capture(manifest, base_dir=tmp_path)

    _write_diagnostic(broken, ads_raw=2_000_000, temperature_c=25.0, sequence_gaps=1)
    with pytest.raises(CalibrationAssemblyError, match="sequence integrity failed"):
        assemble_capture(manifest, base_dir=tmp_path)


def test_tampered_diagnostic_authority_is_rejected(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    source = tmp_path / "current-1.json"
    raw = json.loads(source.read_text(encoding="utf-8"))
    raw["result"]["authority"]["may_apply_calibration"] = True
    source.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(CalibrationAssemblyError, match="authority field may_apply_calibration"):
        assemble_capture(manifest, base_dir=tmp_path)


def test_duplicate_source_within_current_characterization_is_rejected(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest["current"]["points"][1]["diagnostic_file"] = manifest["current"]["points"][0]["diagnostic_file"]
    with pytest.raises(CalibrationAssemblyError, match="reuses diagnostic file"):
        assemble_capture(manifest, base_dir=tmp_path)


def test_duplicate_accelerometer_source_is_rejected(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    source = manifest["accelerometer"]["diagnostic_files"][0]
    manifest["accelerometer"]["diagnostic_files"] = [source, source]
    with pytest.raises(CalibrationAssemblyError, match="accelerometer reuses diagnostic file"):
        assemble_capture(manifest, base_dir=tmp_path)


def test_inconsistent_reported_usable_sample_count_is_rejected(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    source = tmp_path / "current-3.json"
    raw = json.loads(source.read_text(encoding="utf-8"))
    raw["result"]["usable_samples"] += 1
    source.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(CalibrationAssemblyError, match="usable-sample count is inconsistent"):
        assemble_capture(manifest, base_dir=tmp_path)


def test_missing_independent_reference_value_is_rejected(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest["current"]["points"][0].pop("reference_current_a")
    with pytest.raises(CalibrationAssemblyError, match="reference_current_a"):
        assemble_capture(manifest, base_dir=tmp_path)
