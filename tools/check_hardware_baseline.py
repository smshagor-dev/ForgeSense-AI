from __future__ import annotations

import csv
import json
import math
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    baseline = load_json(root / "hardware/profiles/hardware_baseline_v1.json")
    circuit = load_json(root / "hardware/profiles/reference_circuit_v1.json")
    power = load_json(root / "hardware/profiles/power_entry_v1.json")
    support = load_json(root / "hardware/profiles/sensor_support_v1.json")
    devices = load_json(root / "hardware/profiles/sensor_devices_v1.json")
    interconnect = load_json(root / "hardware/profiles/interconnect_v1.json")
    esp = load_json(root / "hardware/profiles/esp32s3_devkit_reference.json")

    assert baseline["schema"] == "forgesense.hardware_baseline.v1"
    assert baseline["revision"] == "HW-BL-004"
    assert circuit["revision"] == "RC-003"
    assert devices["revision"] == "SDEV-001"
    assert baseline["input"]["nominal_v"] == 12.0

    entry = baseline["power"]["entry"]
    assert entry["efuse"] == "TPS259470LRPWR"
    assert entry["tvs"] == "SMBJ15A"
    assert baseline["safety"]["protection_order_a"][0] < entry["current_limit_reference_a"] < baseline["input"]["motor_fuse_a"]
    assert power["efuse"]["reference"] == "TPS259470LRPWR"

    current = baseline["sensing"]["current_shunt"]
    amp = baseline["sensing"]["current_amplifier"]
    adc = baseline["sensing"]["adc"]
    i_ref = float(baseline["input"]["motor_reference_a"])
    shunt = float(current["ohm"])
    gain = float(amp["gain_v_per_v"])
    sense = i_ref * shunt * gain
    fsr = float(adc["differential_fsr_v"])
    assert math.isclose(shunt, 0.015, abs_tol=1e-12)
    assert math.isclose(sense, 0.96, abs_tol=1e-12)
    assert adc["spi_mode"] == 1
    assert adc["target_sample_rate_sps"] == 1000
    assert sense / fsr <= 0.80 + 1e-12
    assert math.isclose(devices["current_frontend"]["reference_output_v"], sense, abs_tol=1e-12)

    comp = baseline["safety"]["comparator"]
    trip_ref = float(comp["supply_v"]) * float(comp["trip_reference_bottom_ohm"]) / (float(comp["trip_reference_top_ohm"]) + float(comp["trip_reference_bottom_ohm"]))
    trip = trip_ref / (shunt * gain)
    assert 3.44 < trip < 3.50
    assert math.isclose(trip, baseline["safety"]["analog_overcurrent_trip_target_a"], abs_tol=0.01)

    assert support["adc"]["reference"] == "ADS131M02IPWR"
    assert support["vibration"]["reference"] == "ADXL355"
    assert support["temperature"]["reference"] == "TMP117AIDRVR"
    assert devices["ads131m02"]["spi_mode"] == 1
    assert devices["adxl355"]["spi_mode"] == 0
    assert devices["tmp117"]["address_7bit"] == 0x48

    link = esp["fpga_link"]
    assert link["tx_gpio"] == 17 and link["rx_gpio"] == 18 and link["baud"] == 115200
    assert link["pin_assignment_validated_on_hardware"] is False

    assert interconnect["revision"] == "INT-002"
    assert interconnect["clock"]["fpga_pin"] == 52
    assert interconnect["reset"]["fpga_pin"] == 4
    assert all(item["fpga_pin"] is not None for item in interconnect["links"])
    assert all(item["fpga_pin_status"] == "frozen_schematic_verified" for item in interconnect["links"])
    assert len({item["fpga_pin"] for item in interconnect["links"]}) == len(interconnect["links"])

    reserved = interconnect["reserved_or_avoided"]
    frozen_pins = {item["fpga_pin"] for item in interconnect["links"]}
    assert frozen_pins.isdisjoint(set(reserved["tf_card_fpga_pins"]))
    assert frozen_pins.isdisjoint(set(reserved["onboard_usb_uart_fpga_pins"]))
    assert frozen_pins.isdisjoint(set(reserved["bank3_1v8_external_fpga_pins"]))

    with (root / "hardware/bom/preliminary_bom_v1.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_ref = {r["RefDes"]: r for r in rows}
    assert "15 mOhm" in by_ref["R_SHUNT"]["Reference part"]
    assert "23.2 kOhm" in by_ref["R_TRIP_TOP"]["Reference part"]
    assert "10.7 kOhm" in by_ref["R_TRIP_BOT"]["Reference part"]
    for ref in ("U_ADC", "U_ACC", "U_TEMP", "U_CS", "U_COMP", "U_EFUSE"):
        assert ref in by_ref

    assert baseline["safety"]["ml_can_override_hard_trip"] is False
    assert baseline["safety"]["monitoring_can_drive_actuator"] is False
    print(f"hardware_baseline_check PASS: current={sense:.3f} V/{fsr:.3f} V FSR, trip={trip:.3f} A, eFuse={entry['current_limit_reference_a']:.3f} A, fuse={baseline['input']['motor_fuse_a']:.1f} A, interconnect={interconnect['revision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
