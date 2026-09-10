from __future__ import annotations

import json
import math
from pathlib import Path


def require(text: str, token: str, path: Path) -> None:
    if token not in text:
        raise AssertionError(f"{path}: missing {token!r}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    contract_path = root / "hardware/profiles/sensor_devices_v1.json"
    cfg = json.loads(contract_path.read_text(encoding="utf-8"))
    assert cfg["schema"] == "forgesense.sensor_devices.v1"
    assert cfg["revision"] == "SDEV-001"

    tmp = cfg["tmp117"]
    assert tmp["address_7bit"] == 0x48
    assert tmp["temp_result_register"] == 0x00
    assert tmp["device_id_register"] == 0x0F
    assert tmp["expected_device_id"] == 0x0117
    assert round(0x0C80 * tmp["lsb_c"] * 10) == 250

    acc = cfg["adxl355"]
    assert (acc["devid_ad"], acc["devid_mst"], acc["part_id"]) == (0xAD, 0x1D, 0xED)
    assert acc["filter_register"] == 0x28 and acc["filter_1khz_value"] == 0x02
    assert acc["range_register"] == 0x2C and acc["range_8g_value"] == 0x03
    assert acc["power_ctl_register"] == 0x2D and acc["measurement_value"] == 0x00
    assert acc["spi_mode"] == 0

    adc = cfg["ads131m02"]
    assert adc["spi_mode"] == 1
    assert adc["word_bits"] == 24 and adc["frame_words"] == 4
    assert adc["expected_id_high_byte"] == 0x22
    assert adc["rreg_id_command"] == 0xA000
    assert adc["wreg_clock_command"] == 0x6180
    assert adc["rreg_clock_command"] == 0xA180
    assert adc["clock_1ksps_hr_value"] == 0x0316
    assert adc["crc_polynomial"] == 0x1021 and adc["crc_seed"] == 0xFFFF
    assert adc["crc_output_required"] is True
    assert math.isclose(adc["differential_fsr_v"], 1.2)

    front = cfg["current_frontend"]
    sense_v = front["reference_current_a"] * front["shunt_ohm"] * front["gain_v_per_v"]
    utilization = sense_v / adc["differential_fsr_v"]
    trip_a = front["trip_reference_v"] / (front["shunt_ohm"] * front["gain_v_per_v"])
    assert math.isclose(sense_v, front["reference_output_v"], abs_tol=1e-12)
    assert utilization <= 0.80 + 1e-12
    assert 3.44 < trip_a < 3.50

    sources = {
        "tmp": root / "fpga/rtl/sensing/tmp117_controller.vhd",
        "acc": root / "fpga/rtl/sensing/adxl355_controller.vhd",
        "adc": root / "fpga/rtl/sensing/ads131m02_controller.vhd",
        "spi0": root / "fpga/rtl/io/spi_mode0_byte_engine.vhd",
        "spi1": root / "fpga/rtl/io/spi_mode1_byte_engine.vhd",
        "i2c": root / "fpga/rtl/io/i2c_byte_engine.vhd",
    }
    text = {key: path.read_text(encoding="utf-8") for key, path in sources.items()}
    for token in ('x"0F"', 'x"0117"'):
        require(text["tmp"], token, sources["tmp"])
    for token in ('x"AD"', 'x"1D"', 'x"ED"', 'x"02"', 'x"03"'):
        require(text["acc"], token, sources["acc"])
    for token in ('x"A000"', 'x"6180"', 'x"A180"', 'x"0316"', 'spi_mode1_byte_engine'):
        require(text["adc"], token, sources["adc"])
    for key in ("spi0", "spi1", "i2c"):
        require(text[key], "freq + denominator - 1", sources[key])

    print(
        "sensor_device_driver_check PASS: "
        f"TMP117 ID=0x{tmp['expected_device_id']:04X}, "
        f"ADXL355 IDs=0x{acc['devid_ad']:02X}/0x{acc['devid_mst']:02X}/0x{acc['part_id']:02X}, "
        f"ADS CLOCK=0x{adc['clock_1ksps_hr_value']:04X}, "
        f"current={sense_v:.3f} V ({utilization*100:.1f}% FSR), trip={trip_a:.3f} A"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
