from __future__ import annotations

import csv
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    interconnect = load_json(root / "hardware/profiles/interconnect_v1.json")
    test_points = load_json(root / "hardware/bringup/test_points_v1.json")
    schema = load_json(root / "hardware/bringup/bench_record_schema_v1.json")
    template = load_json(root / "hardware/bringup/bench_record_template_v1.json")
    smoke_top = (root / "fpga/rtl/top/forgesense_tang_nano_9k_smoke_top.vhd").read_text(encoding="utf-8")
    smoke_build = (root / "fpga/scripts/tang_nano_9k_smoke_build.tcl").read_text(encoding="utf-8")
    cst = (root / "fpga/constraints/tang_nano_9k.cst").read_text(encoding="utf-8")

    with (root / "hardware/bringup/tang_nano_9k_harness_v1.csv").open(newline="", encoding="utf-8") as f:
        harness = list(csv.DictReader(f))

    assert interconnect["revision"] == "INT-002"
    assert test_points["schema"] == "forgesense.bringup_test_points.v1"
    assert schema["record_schema"] == "forgesense.bench_record.v1"
    assert template["schema"] == "forgesense.bench_record.v1"

    harness_ids = [row["HarnessID"] for row in harness]
    assert len(harness_ids) == len(set(harness_ids)), "duplicate harness identifier"
    harness_by_signal = {row["Signal"]: row for row in harness}

    for item in interconnect["links"]:
        signal = item["name"]
        assert signal in harness_by_signal, f"missing harness row for {signal}"
        row = harness_by_signal[signal]
        assert str(item["fpga_pin"]) in row["From"] or str(item["fpga_pin"]) in row["To"], f"{signal}: FPGA pin mismatch"
        assert item["board_header"] in row["From"] or item["board_header"] in row["To"], f"{signal}: header mismatch"

    assert "LOGIC_GND" in harness_by_signal

    point_ids = [point["id"] for point in test_points["points"]]
    assert len(point_ids) == len(set(point_ids)), "duplicate test point identifier"
    point_signals = {point["signal"] for point in test_points["points"]}
    for required in (
        "LOGIC_GND",
        "LOAD_ENABLE",
        "ANALOG_HARD_TRIP",
        "ESTOP_SENSE",
        "ESP32_TO_FPGA_UART",
        "FPGA_TO_ESP32_UART",
        "TMP117_SCL",
        "TMP117_SDA",
        "CS_OUT",
        "ANALOG_TRIP_REF",
    ):
        assert required in point_signals, f"missing bring-up test point for {required}"

    for field in schema["required_fields"]:
        assert field in template, f"bench template missing {field}"
    assert template["overall_result"] == "INCOMPLETE"
    check_ids = {check["check_id"] for check in template["checks"]}
    assert {"BRINGUP-LOAD-OFF", "BRINGUP-UART-ECHO", "BRINGUP-UART-HEARTBEAT"}.issubset(check_ids)

    for token in (
        "load_enable_o <= '0'",
        "tmp_scl_io <= 'Z'",
        "tmp_sda_io <= 'Z'",
        "adxl_cs_n_o <= '1'",
        "ads_cs_n_o <= '1'",
        'tx_byte_i <= x"55"',
        "entity work.uart_rx",
        "entity work.uart_tx",
    ):
        assert token in smoke_top, f"smoke top missing invariant: {token}"

    assert "forgesense_reference_sensor_io" not in smoke_top, "smoke image must not instantiate production sensor/safety composition"
    assert "forgesense_tang_nano_9k_smoke_top" in smoke_build
    assert "tang_nano_9k.cst" in smoke_build and "tang_nano_9k.sdc" in smoke_build
    assert 'IO_LOC "load_enable_o" 29;' in cst
    assert 'IO_PORT "load_enable_o" IO_TYPE=LVCMOS33' in cst

    print(
        "physical_bringup_check PASS: "
        f"{len(harness)} harness rows, {len(point_ids)} test points, safe smoke image, evidence template ready"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
