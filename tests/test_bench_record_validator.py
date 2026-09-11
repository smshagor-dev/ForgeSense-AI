from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.validate_bench_record import validate


def make_record() -> dict:
    return {
        "schema": "forgesense.bench_record.v1",
        "record_id": "BENCH-TEST-001",
        "timestamp_utc": "2026-09-11T00:00:00Z",
        "operator": "test",
        "repository_commit": "a" * 40,
        "board": {
            "fpga_board": "Sipeed Tang Nano 9K",
            "fpga_board_revision": "test",
            "esp32_board": "ESP32-S3-DevKitC-1",
            "sensor_board_revision": "test",
        },
        "image": {
            "top": "forgesense_tang_nano_9k_smoke_top",
            "build_tool": "test",
            "artifact_sha256": "b" * 64,
        },
        "instruments": [
            {
                "type": "DMM",
                "manufacturer_model": "test",
                "asset_or_serial": "test",
                "calibration_status": "test",
            }
        ],
        "supply": [
            {
                "rail": "logic_only",
                "set_voltage_v": 5.0,
                "current_limit_a": 0.5,
                "measured_idle_current_a": 0.1,
            }
        ],
        "checks": [
            {
                "check_id": "BRINGUP-LOAD-OFF",
                "result": "PASS",
                "expected": "low",
                "observed": "low",
                "units": "logic",
                "evidence": [
                    {
                        "file": "capture.txt",
                        "sha256": "c" * 64,
                        "description": "synthetic validator fixture",
                    }
                ],
            }
        ],
        "overall_result": "PASS",
        "notes": "synthetic unit-test record; not physical evidence",
    }


def write_record(tmp_path: Path, record: dict) -> Path:
    path = tmp_path / "record.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def test_valid_bench_record(tmp_path: Path) -> None:
    record_path = write_record(tmp_path, make_record())
    validate(record_path, Path("hardware/bringup/bench_record_schema_v1.json"))


def test_pass_record_rejects_failed_check(tmp_path: Path) -> None:
    record = make_record()
    record["checks"][0]["result"] = "FAIL"
    record_path = write_record(tmp_path, record)
    with pytest.raises(ValueError, match="PASS record contains"):
        validate(record_path, Path("hardware/bringup/bench_record_schema_v1.json"))


def test_bad_artifact_hash_is_rejected(tmp_path: Path) -> None:
    record = make_record()
    record["image"]["artifact_sha256"] = "not-a-hash"
    record_path = write_record(tmp_path, record)
    with pytest.raises(ValueError, match="artifact_sha256"):
        validate(record_path, Path("hardware/bringup/bench_record_schema_v1.json"))
