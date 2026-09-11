from __future__ import annotations

import json
import re
from pathlib import Path


EXPECTED = {
    "clk_27m_i": (52, None),
    "reset_n_i": (4, None),
    "esp32_uart_rx_i": (25, "J5-5"),
    "esp32_uart_tx_o": (26, "J5-6"),
    "analog_hard_trip_i": (27, "J5-7"),
    "estop_sense_i": (28, "J5-8"),
    "load_enable_o": (29, "J5-9"),
    "recovery_req_i": (30, "J5-10"),
    "tmp_scl_io": (33, "J5-11"),
    "tmp_sda_io": (34, "J5-12"),
    "adxl_cs_n_o": (40, "J5-13"),
    "adxl_sclk_o": (35, "J5-14"),
    "adxl_mosi_o": (41, "J5-15"),
    "adxl_miso_i": (42, "J5-16"),
    "adxl_drdy_i": (51, "J5-17"),
    "ads_cs_n_o": (53, "J5-18"),
    "ads_sclk_o": (54, "J5-19"),
    "ads_din_o": (55, "J5-20"),
    "ads_dout_i": (56, "J5-21"),
    "ads_drdy_n_i": (57, "J5-22"),
}

INTERCONNECT_NAMES = {
    "esp32_uart_rx_i": "ESP32_TO_FPGA_UART",
    "esp32_uart_tx_o": "FPGA_TO_ESP32_UART",
    "analog_hard_trip_i": "ANALOG_HARD_TRIP",
    "estop_sense_i": "ESTOP_SENSE",
    "load_enable_o": "LOAD_ENABLE",
    "recovery_req_i": "RECOVERY_REQUEST",
    "tmp_scl_io": "TMP117_SCL",
    "tmp_sda_io": "TMP117_SDA",
    "adxl_cs_n_o": "ADXL355_CS_N",
    "adxl_sclk_o": "ADXL355_SCLK",
    "adxl_mosi_o": "ADXL355_MOSI",
    "adxl_miso_i": "ADXL355_MISO",
    "adxl_drdy_i": "ADXL355_DRDY",
    "ads_cs_n_o": "ADS131M02_CS_N",
    "ads_sclk_o": "ADS131M02_SCLK",
    "ads_din_o": "ADS131M02_DIN",
    "ads_dout_i": "ADS131M02_DOUT",
    "ads_drdy_n_i": "ADS131M02_DRDY_N",
}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    cst = (root / "fpga/constraints/tang_nano_9k.cst").read_text(encoding="utf-8")
    sdc = (root / "fpga/constraints/tang_nano_9k.sdc").read_text(encoding="utf-8")
    top = (root / "fpga/rtl/top/forgesense_tang_nano_9k_top.vhd").read_text(encoding="utf-8")
    interconnect = json.loads((root / "hardware/profiles/interconnect_v1.json").read_text(encoding="utf-8"))

    locations = {name: int(pin) for name, pin in re.findall(r'IO_LOC\s+"([^"]+)"\s+(\d+)\s*;', cst)}
    assert locations == {name: pin for name, (pin, _) in EXPECTED.items()}, locations
    assert len(set(locations.values())) == len(locations), "duplicate FPGA pin assignment"

    external_pins = {pin for name, (pin, header) in EXPECTED.items() if header is not None}
    assert not external_pins.intersection({17, 18, 36, 37, 38, 39}), "reserved onboard interface pin reused"
    assert not external_pins.intersection(set(range(79, 87))), "1.8 V BANK3 pin reused for 3.3 V external wiring"

    assert 'IO_PORT "reset_n_i" IO_TYPE=LVCMOS18' in cst
    for name, (_, header) in EXPECTED.items():
        if header is not None:
            assert f'IO_PORT "{name}" IO_TYPE=LVCMOS33' in cst, f"{name}: missing LVCMOS33 constraint"

    assert "create_clock -name clk_27m -period 37.037" in sdc
    assert "[get_ports {clk_27m_i}]" in sdc

    links = {item["name"]: item for item in interconnect["links"]}
    assert interconnect["revision"] == "INT-002"
    for port_name, link_name in INTERCONNECT_NAMES.items():
        pin, header = EXPECTED[port_name]
        item = links[link_name]
        assert item["fpga_pin"] == pin
        assert item["board_header"] == header
        assert item["fpga_pin_status"] == "frozen_schematic_verified"

    assert interconnect["clock"]["fpga_pin"] == 52
    assert interconnect["reset"]["fpga_pin"] == 4
    assert interconnect["reset"]["io_voltage_v"] == 1.8

    # Physical-top safety and electrical semantics must remain explicit.
    for token in (
        "hard_trip_sync_inst : entity work.input_sync",
        "estop_sync_inst : entity work.input_sync",
        "recovery_sync_inst : entity work.input_sync",
        "tmp_scl_io <= '0' when tmp_scl_drive_low_i = '1' else 'Z'",
        "tmp_sda_io <= '0' when tmp_sda_drive_low_i = '1' else 'Z'",
        "physical E-stop gate",
    ):
        assert token in top, f"physical top missing required invariant: {token}"

    print("tang_nano_9k_pinmap_check PASS: 20 constrained ports, J5-5..J5-22 application mapping frozen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
