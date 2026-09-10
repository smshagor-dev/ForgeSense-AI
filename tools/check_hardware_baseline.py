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
    interconnect = load_json(root / "hardware/profiles/interconnect_v1.json")
    esp = load_json(root / "hardware/profiles/esp32s3_devkit_reference.json")
    schematic = load_json(root / "hardware/kicad/schematic_contract_v1.json")

    assert baseline["schema"] == "forgesense.hardware_baseline.v1"
    assert baseline["revision"] == "HW-BL-002"
    assert circuit["revision"] == "RC-002"
    assert schematic["schema"] == "forgesense.schematic_contract.v1"

    buck = baseline["power"]["buck_5v"]
    assert buck["reference"] == "TPS54202"
    assert buck["vin_min_v"] < baseline["input"]["nominal_v"] < buck["vin_max_v"]
    assert buck["output_v"] == 5.0 and buck["output_current_a"] >= 2.0
    assert buck["inductor_uH"] == 15.0
    assert buck["cout_uF_each"] * buck["cout_count"] >= 44.0
    assert buck["feedback_top_ohm"] == 100000.0
    assert buck["feedback_bottom_ohm"] == 13300.0

    quiet = baseline["power"]["quiet_3v3"]
    assert quiet["reference"] == "TPS7A2033"
    assert quiet["output_v"] == baseline["input"]["logic_v"]
    assert quiet["output_current_a"] >= 0.3
    assert quiet["cout_uF"] >= quiet["minimum_stable_cout_uF"]

    current = baseline["sensing"]["current_shunt"]
    amp = baseline["sensing"]["current_amplifier"]
    i_ref = baseline["input"]["motor_reference_a"]
    shunt_v = i_ref * current["ohm"]
    sense_v = shunt_v * amp["gain_v_per_v"]
    shunt_power = i_ref * i_ref * current["ohm"]
    assert math.isclose(shunt_v, 0.08, rel_tol=0, abs_tol=1e-9)
    assert math.isclose(sense_v, 1.6, rel_tol=0, abs_tol=1e-9)
    assert current["minimum_power_w"] >= 3.0 * shunt_power

    comp = baseline["safety"]["comparator"]
    trip_ref = comp["supply_v"] * comp["trip_reference_bottom_ohm"] / (
        comp["trip_reference_top_ohm"] + comp["trip_reference_bottom_ohm"]
    )
    trip_a = trip_ref / (current["ohm"] * amp["gain_v_per_v"])
    assert 1.70 < trip_ref < 1.75
    assert 3.40 < trip_a < 3.55
    assert trip_a > i_ref
    assert trip_a < baseline["input"]["motor_fuse_a"]
    assert comp["hysteresis_footprint"].startswith("DNI")

    gate = baseline["safety"]["gate_driver"]
    switch = baseline["safety"]["motor_switch"]
    fly = baseline["safety"]["flyback"]
    estop = baseline["safety"]["estop"]
    assert gate["reference"] == "UCC27511A" and gate["supply_v"] == 5.0
    assert gate["command_input"] == "IN+" and gate["hardware_inhibit_input"] == "IN-"
    assert switch["vds_v"] >= 5.0 * baseline["input"]["nominal_v"]
    assert switch["rds_on_max_mohm_at_4v5"] <= 5.0
    assert fly["vrrm_v"] >= switch["vds_v"]
    assert fly["forward_average_a"] >= baseline["input"]["motor_fuse_a"]
    assert estop["contact"] == "normally_closed"
    assert estop["hardware_gate_inhibit"] is True
    assert estop["fault_action"].startswith("10k_pullup")
    assert baseline["safety"]["ml_can_override_hard_trip"] is False

    assert baseline["sensing"]["adc"]["max_sample_rate_sps"] == 64000
    assert baseline["sensing"]["vibration"]["raw_sample_rate_hz"] == 1000
    assert baseline["sensing"]["temperature"]["supply_v"] == 3.3

    link = esp["fpga_link"]
    assert link["tx_gpio"] == 17 and link["rx_gpio"] == 18
    assert link["baud"] == baseline["compute"]["edge"]["baud"]
    assert link["pin_assignment_documentation_verified"] is True
    assert link["pin_assignment_validated_on_hardware"] is False

    for item in interconnect["links"]:
        assert item["fpga_pin"] is None
        assert item["fpga_pin_status"] == "pending_board_header_freeze"

    nets = schematic["critical_nets"]
    assert nets["ESTOP_INHIBIT_5V"]["default"] == "HIGH_DISABLE"
    assert nets["ESTOP_INHIBIT_5V"]["must_not_depend_on_fpga_clock"] is True
    assert nets["FPGA_LOAD_ENABLE"]["hardware_estop_can_override"] is True
    assert nets["ANALOG_HARD_TRIP"]["destination"] == "FPGA"

    with (root / "hardware/bom/preliminary_bom_v1.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    parts = {row["Reference part"] for row in rows}
    for required in (
        "TPS54202", "TPS7A2033", "INA181A1", "TLV3201", "ADS131M02",
        "ADXL355", "TMP117", "SN74LVC1G17", "UCC27511A",
        "CSD18540Q5B", "STPS5L60",
    ):
        assert required in parts

    print(
        "hardware_baseline_check PASS: "
        f"CS={sense_v:.3f} V @ {i_ref:.2f} A, "
        f"trip_ref={trip_ref:.3f} V, trip={trip_a:.2f} A, "
        f"buck={buck['output_v']:.1f} V/{buck['output_current_a']:.1f} A"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
