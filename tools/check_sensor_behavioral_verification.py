from __future__ import annotations

from pathlib import Path


def require(path: Path, tokens: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    for token in tokens:
        if token not in text:
            raise AssertionError(f"{path}: missing required token {token!r}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]

    tmp_model = root / "fpga/tb/models/tmp117_i2c_model.vhd"
    adxl_model = root / "fpga/tb/models/adxl355_spi_model.vhd"
    ads_model = root / "fpga/tb/models/ads131m02_spi_model.vhd"

    tmp_tb = root / "fpga/tb/tb_tmp117_controller_behavioral.vhd"
    adxl_tb = root / "fpga/tb/tb_adxl355_controller_behavioral.vhd"
    ads_tb = root / "fpga/tb/tb_ads131m02_controller_behavioral.vhd"
    cluster_tb = root / "fpga/tb/tb_selected_sensor_cluster_behavioral.vhd"

    require(tmp_model, ("force_nack", "force_bad_id", "x\"0117\"", "temperature_raw"))
    require(adxl_model, ("force_bad_id", "force_bad_config", "x\"AD\"", "x\"1D\"", "x\"ED\""))
    require(ads_model, ("force_bad_id", "force_bad_crc", "force_bad_clock", "crc16_next", "RESP_CLOCK"))

    require(tmp_tb, ("wrong identity was not rejected", "NACK was not surfaced", "to_signed(250, 16)"))
    require(adxl_tb, ("configuration readback corruption was not rejected", "to_signed(312, 16)"))
    require(ads_tb, ("CRC corruption was not rejected", "CLOCK readback corruption was not rejected", "x\"05A0\""))
    require(cluster_tb, ("TMP117 cluster sample mismatch", "ADXL355 cluster sample mismatch", "ADS131M02 cluster channel mismatch"))

    print("sensor_behavioral_verification_check PASS: 3 device models, 3 fault suites, 1 combined cluster suite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
