from __future__ import annotations

import csv
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    baseline = load_json(root / "hardware/profiles/hardware_baseline_v1.json")
    circuits = load_json(root / "hardware/profiles/reference_circuit_v1.json")
    interconnect = load_json(root / "hardware/profiles/interconnect_v1.json")
    esp32 = load_json(root / "hardware/profiles/esp32s3_devkit_reference.json")

    assert baseline["schema"] == "forgesense.hardware_baseline.v1"
    assert baseline["status"] == "pre_hardware_reference"
    assert baseline["input"]["nominal_v"] == circuits["nominal_input_v"] == 12.0
    assert baseline["input"]["logic_v"] == circuits["logic_v"] == interconnect["logic_voltage_v"] == 3.3

    amp = baseline["sensing"]["current_amplifier"]
    shunt = baseline["sensing"]["current_shunt"]
    assert amp["reference"] == "INA181A1"
    assert amp["gain_v_per_v"] == circuits["current_sense"]["gain"] == 20.0
    assert shunt["ohm"] == circuits["current_sense"]["shunt_ohm"] == 0.025
    assert shunt["kelvin_required"] is True
    assert baseline["sensing"]["adc"]["resolution_bits"] == 24
    assert baseline["sensing"]["adc"]["reference_max_sample_rate_sps"] == 32000

    edge = baseline["compute"]["edge"]
    assert edge["fpga_uart_tx_gpio"] == esp32["fpga_link"]["tx_gpio"] == 17
    assert edge["fpga_uart_rx_gpio"] == esp32["fpga_link"]["rx_gpio"] == 18
    assert esp32["fpga_link"]["pin_assignment_documentation_verified"] is True
    assert esp32["fpga_link"]["pin_assignment_validated_on_hardware"] is False

    links = {entry["name"]: entry for entry in interconnect["links"]}
    assert links["FPGA_TO_ESP32_UART"]["esp32_gpio"] == 18
    assert links["ESP32_TO_FPGA_UART"]["esp32_gpio"] == 17
    for name in ("FPGA_TO_ESP32_UART", "ESP32_TO_FPGA_UART", "ANALOG_HARD_TRIP", "ESTOP_SENSE", "LOAD_ENABLE"):
        assert links[name]["fpga_pin"] is None
        assert links[name]["fpga_pin_status"] == "pending_board_header_freeze"
    assert interconnect["clock"]["fpga_pin"] == 52
    assert interconnect["clock"]["frequency_hz"] == baseline["compute"]["fpga"]["clock_hz"] == 27000000

    safety = baseline["safety"]
    assert safety["analog_trip_target"] == "fpga_external_hard_trip"
    assert safety["estop_physical_gate_inhibit"] is True
    assert safety["ml_can_override_hard_trip"] is False
    assert safety["monitoring_can_drive_actuator"] is False

    with (root / "hardware/bom/preliminary_bom_v1.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    parts = {row["Reference part"] for row in rows}
    required = {"Sipeed Tang Nano 9K", "ESP32-S3-DevKitC-1", "INA181A1", "ADS131M02", "ADXL355", "TMP117"}
    assert required.issubset(parts)

    current = circuits["current_sense"]
    i_ref = baseline["input"]["motor_reference_a"]
    shunt_v = i_ref * current["shunt_ohm"]
    amp_v = shunt_v * current["gain"]
    shunt_w = i_ref * i_ref * current["shunt_ohm"]
    trip_a = current["backup_trip_reference_v"] / (current["shunt_ohm"] * current["gain"])
    assert abs(shunt_v - 0.08) < 1e-9
    assert abs(amp_v - 1.6) < 1e-9
    assert abs(shunt_w - 0.256) < 1e-9
    assert 3.4 < trip_a < 3.5

    print(
        "hardware_baseline_check PASS: "
        f"shunt={shunt_v:.3f} V amp={amp_v:.3f} V "
        f"shunt_power={shunt_w:.3f} W trip={trip_a:.2f} A"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
