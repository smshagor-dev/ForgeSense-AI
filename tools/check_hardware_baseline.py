from __future__ import annotations

import csv
import json
import math
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    baseline = load_json(root / "hardware/profiles/hardware_baseline_v1.json")
    circuit = load_json(root / "hardware/profiles/reference_circuit_v1.json")
    interconnect = load_json(root / "hardware/profiles/interconnect_v1.json")
    esp = load_json(root / "hardware/profiles/esp32s3_devkit_reference.json")
    power_entry = load_json(root / "hardware/profiles/power_entry_v1.json")
    sensor_support = load_json(root / "hardware/profiles/sensor_support_v1.json")
    schematic = load_json(root / "hardware/kicad/schematic_contract_v1.json")
    bom_rows = load_csv(root / "hardware/bom/preliminary_bom_v1.csv")
    package_rows = load_csv(root / "hardware/kicad/component_packages_v1.csv")
    endpoint_rows = load_csv(root / "hardware/kicad/net_endpoints_v1.csv")

    assert baseline["schema"] == "forgesense.hardware_baseline.v1"
    assert baseline["revision"] == "HW-BL-003"
    assert circuit["revision"] == "RC-002"
    assert power_entry["schema"] == "forgesense.power_entry.v1"
    assert power_entry["revision"] == "PWR-IN-001"
    assert sensor_support["schema"] == "forgesense.sensor_support.v1"
    assert sensor_support["revision"] == "SNS-SUP-001"
    assert schematic["schema"] == "forgesense.schematic_contract.v1"
    assert schematic["revision"] == "SCH-CON-002"

    # Protected 12 V entry: passive fuse -> TVS -> eFuse -> protected bus.
    assert power_entry["protection_order"] == [
        "connector",
        "5A_passive_fuse",
        "SMBJ15A_TVS",
        "TPS259470L_eFuse",
        "VIN_12V_PROTECTED",
    ]
    assert power_entry["input"]["nominal_v"] == baseline["input"]["nominal_v"]
    assert power_entry["input"]["passive_fuse_a"] == baseline["input"]["motor_fuse_a"]

    tvs = power_entry["tvs"]
    efuse = power_entry["efuse"]
    assert tvs["reference"] == "Littelfuse SMBJ15A"
    assert tvs["reverse_standoff_v"] > power_entry["input"]["nominal_v"]
    assert tvs["clamp_max_v_at_ipp"] < efuse["vin_abs_max_v"]
    assert efuse["reference"] == "TPS259470LRPWR"
    assert efuse["vin_operating_v"][0] < power_entry["input"]["nominal_v"] < efuse["vin_operating_v"][1]
    assert efuse["reverse_polarity_protection"] is True
    assert efuse["true_reverse_current_blocking"] is True
    assert efuse["must_not_enable_motor"] is True

    r1 = float(efuse["uvlo"]["r1_top_ohm"])
    r2 = float(efuse["uvlo"]["r2_mid_ohm"])
    r3 = float(efuse["uvlo"]["r3_bottom_ohm"])
    vref = float(efuse["uvlo"]["threshold_reference_v"])
    uvlo = vref * (r1 + r2 + r3) / (r2 + r3)
    ovlo = vref * (r1 + r2 + r3) / r3
    assert math.isclose(uvlo, 9.0333333333, rel_tol=0, abs_tol=1e-9)
    assert math.isclose(ovlo, 18.0666666667, rel_tol=0, abs_tol=1e-9)
    assert math.isclose(uvlo, baseline["power"]["entry"]["uvlo_reference_v"], rel_tol=0, abs_tol=1e-9)
    assert math.isclose(ovlo, baseline["power"]["entry"]["ovlo_reference_v"], rel_tol=0, abs_tol=1e-9)

    ilim = float(efuse["overcurrent"]["equation_numerator"]) / float(efuse["overcurrent"]["rilm_ohm"])
    assert math.isclose(ilim, efuse["overcurrent"]["expected_from_rilm_a"], rel_tol=0, abs_tol=1e-9)
    assert math.isclose(ilim, baseline["power"]["entry"]["current_limit_reference_a"], rel_tol=0, abs_tol=1e-9)

    blanking_ms = (
        float(efuse["blanking"]["itimer_cap_nf"])
        * float(efuse["blanking"]["reference_delta_v"])
        / float(efuse["blanking"]["reference_discharge_current_uA"])
    )
    dvdt_v_per_ms = float(efuse["slew"]["reference_equation_constant"]) / float(efuse["slew"]["dvdt_cap_pf"])
    rise_ms = power_entry["input"]["nominal_v"] / dvdt_v_per_ms
    assert 9.5 < blanking_ms < 10.5
    assert math.isclose(dvdt_v_per_ms, efuse["slew"]["approx_v_per_ms"], rel_tol=0, abs_tol=1e-9)
    assert math.isclose(rise_ms, efuse["slew"]["approx_12v_rise_ms"], rel_tol=0, abs_tol=1e-9)

    buck = baseline["power"]["buck_5v"]
    assert buck["reference"] == "TPS54202DDCR"
    assert buck["vin_min_v"] < baseline["input"]["nominal_v"] < buck["vin_max_v"]
    assert buck["output_v"] == 5.0 and buck["output_current_a"] >= 2.0
    assert buck["inductor_uH"] == 15.0
    assert buck["cout_uF_each"] * buck["cout_count"] >= 44.0
    assert buck["feedback_top_ohm"] == 100000.0
    assert buck["feedback_bottom_ohm"] == 13300.0

    quiet = baseline["power"]["quiet_3v3"]
    assert quiet["reference"] == "TPS7A2033PDBVR"
    assert quiet["output_v"] == baseline["input"]["logic_v"]
    assert quiet["output_current_a"] >= 0.3
    assert quiet["cout_uF"] >= quiet["minimum_stable_cout_uF"]

    current = baseline["sensing"]["current_shunt"]
    amp = baseline["sensing"]["current_amplifier"]
    i_ref = float(baseline["input"]["motor_reference_a"])
    shunt_v = i_ref * float(current["ohm"])
    sense_v = shunt_v * float(amp["gain_v_per_v"])
    shunt_power = i_ref * i_ref * float(current["ohm"])
    assert math.isclose(shunt_v, 0.08, rel_tol=0, abs_tol=1e-9)
    assert math.isclose(sense_v, 1.6, rel_tol=0, abs_tol=1e-9)
    assert float(current["minimum_power_w"]) >= 3.0 * shunt_power

    comp = baseline["safety"]["comparator"]
    trip_ref = float(comp["supply_v"]) * float(comp["trip_reference_bottom_ohm"]) / (
        float(comp["trip_reference_top_ohm"]) + float(comp["trip_reference_bottom_ohm"])
    )
    trip_a = trip_ref / (float(current["ohm"]) * float(amp["gain_v_per_v"]))
    assert 1.70 < trip_ref < 1.75
    assert 3.40 < trip_a < 3.55
    assert trip_a < ilim < float(baseline["input"]["motor_fuse_a"])
    assert baseline["safety"]["protection_order_a"] == [3.46, 4.0412121212, 5.0]
    assert comp["hysteresis_footprint"].startswith("DNI")

    gate = baseline["safety"]["gate_driver"]
    switch = baseline["safety"]["motor_switch"]
    fly = baseline["safety"]["flyback"]
    estop = baseline["safety"]["estop"]
    assert gate["reference"] == "UCC27511ADBVR" and gate["supply_v"] == 5.0
    assert gate["command_input"] == "IN+" and gate["hardware_inhibit_input"] == "IN-"
    assert float(switch["vds_v"]) >= 5.0 * float(baseline["input"]["nominal_v"])
    assert float(switch["rds_on_max_mohm_at_4v5"]) <= 5.0
    assert float(fly["vrrm_v"]) >= float(switch["vds_v"])
    assert float(fly["forward_average_a"]) >= float(baseline["input"]["motor_fuse_a"])
    assert estop["contact"] == "normally_closed"
    assert estop["hardware_gate_inhibit"] is True
    assert estop["fault_action"].startswith("10k_pullup")
    assert baseline["safety"]["ml_can_override_hard_trip"] is False

    adc = sensor_support["adc"]
    assert adc["reference"] == "ADS131M02IPWR"
    assert adc["avdd_decoupling_uF"] >= 1.0
    assert adc["dvdd_decoupling_uF"] >= 1.0
    assert adc["cap_pin_to_dgnd_nf"] == 220.0
    assert adc["clock"]["frequency_hz"] == 8192000
    assert adc["spi"]["crc_required_in_firmware_or_rtl"] is True
    assert baseline["sensing"]["adc"]["max_sample_rate_sps"] == 64000

    vibration = sensor_support["vibration"]
    assert vibration["reference"] == "ADXL355"
    assert vibration["spi"]["cpol"] == 0 and vibration["spi"]["cpha"] == 0
    assert vibration["spi"]["clock_hz_target"] <= vibration["spi"]["clock_hz_max_datasheet"]
    assert vibration["spi"]["shared_bus_requires_gated_sclk"] is True
    assert vibration["measurement"]["raw_odr_hz"] == 1000
    assert vibration["measurement"]["startup_discharge_ms_min"] >= 200

    temperature = sensor_support["temperature"]
    assert temperature["reference"] == "TMP117AIDRVR"
    assert temperature["bypass_uF"] >= 0.1
    assert temperature["address_select"] == "ADD0_to_GND"
    assert temperature["i2c"]["scl_pullup_ohm"] == 4990.0
    assert temperature["i2c"]["sda_pullup_ohm"] == 4990.0
    assert temperature["i2c"]["alert_pullup_ohm"] == 4990.0
    assert temperature["alert"]["not_a_replacement_for_fpga_normalized_temperature_hard_limit"] is True

    link = esp["fpga_link"]
    assert link["tx_gpio"] == 17 and link["rx_gpio"] == 18
    assert link["baud"] == baseline["compute"]["edge"]["baud"]
    assert link["pin_assignment_documentation_verified"] is True
    assert link["pin_assignment_validated_on_hardware"] is False

    for item in interconnect["links"]:
        assert item["fpga_pin"] is None
        assert item["fpga_pin_status"] == "pending_board_header_freeze"

    nets = schematic["critical_nets"]
    assert nets["VIN_12V_PROTECTED"]["source"] == "TPS259470L"
    assert math.isclose(nets["VIN_12V_PROTECTED"]["current_limit_a_reference"], ilim, rel_tol=0, abs_tol=1e-9)
    assert nets["ESTOP_INHIBIT_5V"]["default"] == "HIGH_DISABLE"
    assert nets["ESTOP_INHIBIT_5V"]["must_not_depend_on_fpga_clock"] is True
    assert nets["FPGA_LOAD_ENABLE"]["hardware_estop_can_override"] is True
    assert nets["ANALOG_HARD_TRIP"]["destination"] == "FPGA"
    assert nets["ADC_CLK_8M192"]["frequency_hz"] == 8192000

    bom_parts = {row["Reference part"] for row in bom_rows}
    for required in (
        "SMBJ15A",
        "TPS259470LRPWR",
        "TPS54202DDCR",
        "TPS7A2033PDBVR",
        "INA181A1IDBVR",
        "TLV3201AIDBVR",
        "ADS131M02IPWR",
        "SiT8924BA-22-33E-8.192000",
        "ADXL355BEZ",
        "TMP117AIDRVR",
        "SN74LVC1G17DBVR",
        "UCC27511ADBVR",
        "CSD18540Q5B",
        "STPS5L60U",
    ):
        assert required in bom_parts

    package_mpns = {row["Orderable MPN"] for row in package_rows}
    for required in (
        "TPS259470LRPWR",
        "SMBJ15A",
        "TPS54202DDCR",
        "TPS7A2033PDBVR",
        "INA181A1IDBVR",
        "TLV3201AIDBVR",
        "ADS131M02IPWR",
        "SiT8924BA-22-33E-8.192000",
        "ADXL355BEZ",
        "TMP117AIDRVR",
        "SN74LVC1G17DBVR",
        "UCC27511ADBVR",
        "CSD18540Q5B",
        "STPS5L60U",
    ):
        assert required in package_mpns
    assert all(row["Capture status"] == "package_verified_footprint_binding_pending" for row in package_rows)

    endpoint_by_net = {row["Net"]: row for row in endpoint_rows}
    for required_net in (
        "VIN_12V_RAW", "VIN_12V_PROTECTED", "+5V_LOGIC", "+3V3_QUIET",
        "CS_OUT", "ANALOG_HARD_TRIP", "ESTOP_INHIBIT_5V", "FPGA_LOAD_ENABLE",
        "ADC_CLK_8M192", "ADC_SPI_SCLK", "ACC_SPI_SCLK", "TEMP_I2C_SCL",
    ):
        assert required_net in endpoint_by_net
    for net in (
        "ANALOG_HARD_TRIP", "FPGA_ESTOP_SENSE", "FPGA_LOAD_ENABLE",
        "FPGA_UART_TX", "ESP32_UART_TX", "ADC_SPI_SCLK", "ADC_SPI_MOSI",
        "ADC_SPI_MISO", "ADC_CS_N", "ADC_DRDY", "ACC_SPI_SCLK",
        "ACC_SPI_MOSI", "ACC_SPI_MISO", "ACC_CS_N", "ACC_DRDY",
    ):
        assert "pending" in endpoint_by_net[net]["Freeze status"]

    print(
        "hardware_baseline_check PASS: "
        f"UVLO={uvlo:.2f} V, OVLO={ovlo:.2f} V, eFuse={ilim:.2f} A, "
        f"CS={sense_v:.3f} V @ {i_ref:.2f} A, trip={trip_a:.2f} A, "
        f"ADCclk={adc['clock']['frequency_hz'] / 1_000_000:.3f} MHz"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
