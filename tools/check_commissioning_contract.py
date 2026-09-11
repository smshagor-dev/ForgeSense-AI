from __future__ import annotations

from pathlib import Path


def text(root: Path, path: str) -> str:
    return (root / path).read_text(encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]

    platform = text(root, "fpga/rtl/top/forgesense_platform_core.vhd")
    board = text(root, "fpga/rtl/top/forgesense_board_core.vhd")
    sensor = text(root, "fpga/rtl/top/forgesense_sensor_board_core.vhd")
    phy = text(root, "fpga/rtl/top/forgesense_phy_board_core.vhd")
    selected = text(root, "fpga/rtl/top/forgesense_reference_sensor_io.vhd")
    py_protocol = text(root, "protocol/python/forgesense_protocol.py")
    cpp_protocol = text(root, "firmware/components/forgesense_protocol/include/forgesense_protocol.h")
    core = text(root, "commissioning/forgesense_commission/core.py")
    cli = text(root, "commissioning/forgesense_commission/cli.py")
    bridge = text(root, "firmware/esp32_commissioning/main/app_main.cpp")
    bridge_cmake = text(root, "firmware/esp32_commissioning/main/CMakeLists.txt")
    bridge_config = text(root, "firmware/esp32_commissioning/sdkconfig.defaults")
    cpp_test = text(root, "firmware/tests/commissioning_status_test.cpp")
    spec = text(root, "protocol/SPEC_V1.md")
    tests = text(root, "tests/test_commissioning.py")
    schema = text(root, "hardware/bringup/bench_record_schema_v1.json")

    expected_vhdl = {
        7: "device_identity_ok",
        8: "device_transport_error",
        9: "device_diagnostics(0)",
        10: "device_diagnostics(1)",
        11: "device_diagnostics(2)",
        12: "device_diagnostics(3)",
        13: "device_diagnostics(4)",
        14: "device_diagnostics(5)",
    }
    for bit, source in expected_vhdl.items():
        assert f"safety_flags_i({bit}) <= {source};" in platform
    assert "safety_flags_i(15) <= '0';" in platform

    for source in (board, sensor, phy):
        assert "device_identity_ok" in source
        assert "device_transport_error" in source
        assert "device_diagnostics" in source
    assert "device_identity_i <= tmp_ok and adxl_ok and ads_ok;" in selected
    assert "device_transport_error_i <= tmp_error or adxl_error or ads_error;" in selected
    assert "device_diagnostics_i <= ads_error & adxl_error & tmp_error & ads_ok & adxl_ok & tmp_ok;" in selected

    py_masks = {
        "SAFETY_DEVICE_IDENTITY_OK": "0x0080",
        "SAFETY_DEVICE_TRANSPORT_ERROR": "0x0100",
        "SAFETY_TMP117_TRUSTED": "0x0200",
        "SAFETY_ADXL355_TRUSTED": "0x0400",
        "SAFETY_ADS131M02_TRUSTED": "0x0800",
        "SAFETY_TMP117_ERROR": "0x1000",
        "SAFETY_ADXL355_ERROR": "0x2000",
        "SAFETY_ADS131M02_ERROR": "0x4000",
    }
    for name, value in py_masks.items():
        assert f"{name} = {value}" in py_protocol

    cpp_masks = {
        "kSafetyDeviceIdentityOk": "0x0080",
        "kSafetyDeviceTransportError": "0x0100",
        "kSafetyTmp117Trusted": "0x0200",
        "kSafetyAdxl355Trusted": "0x0400",
        "kSafetyAds131m02Trusted": "0x0800",
        "kSafetyTmp117Error": "0x1000",
        "kSafetyAdxl355Error": "0x2000",
        "kSafetyAds131m02Error": "0x4000",
    }
    for name, value in cpp_masks.items():
        assert f"{name} = {value}" in cpp_protocol

    for method in (
        "device_identity_ok()",
        "device_transport_error()",
        "tmp117_trusted()",
        "adxl355_trusted()",
        "ads131m02_trusted()",
        "tmp117_error()",
        "adxl355_error()",
        "ads131m02_error()",
    ):
        assert method in cpp_protocol

    observe_start = core.index("def observe_production_stream")
    observe_end = core.index("def _find_check")
    observe_source = core[observe_start:observe_end]
    assert ".write(" not in observe_source, "production observation must remain read-only"
    assert "transport.write" in core, "smoke echo test must exercise TX"
    assert "def selected_devices_pass" in core
    assert "def sequence_integrity_pass" in core
    assert "def link_error_rate" in core
    assert "self.selected_devices_pass" in core
    assert "self.sequence_integrity_pass" in core
    assert "--esp32-board-revision" in cli
    assert "exit_code = 0 if observer.commissioning_pass else 2" in cli

    assert "kFpgaTxGpio = 17" in bridge
    assert "kFpgaRxGpio = 18" in bridge
    assert "kBaud = 115200" in bridge
    assert "usb_serial_jtag_read_bytes" in bridge
    assert "usb_serial_jtag_write_bytes" in bridge
    assert "uart_read_bytes" in bridge
    assert "uart_write_bytes" in bridge
    assert "wifi" not in bridge.lower()
    assert "esp_driver_usb_serial_jtag" in bridge_cmake
    assert "CONFIG_LOG_DEFAULT_LEVEL_NONE=y" in bridge_config
    assert "CONFIG_ESP_CONSOLE_NONE=y" in bridge_config

    assert "0xC0, 0x0E" in cpp_test
    assert "tmp117_trusted()" in cpp_test
    assert "adxl355_trusted()" in cpp_test
    assert "ads131m02_trusted()" in cpp_test
    assert "!parsed.status.ads131m02_error()" in cpp_test

    for token in (
        "TMP117 trusted/configured",
        "ADXL355 trusted/configured",
        "ADS131M02 trusted/configured",
        "TMP117 transport error",
        "ADXL355 initialization/transport error",
        "ADS131M02 frame/configuration error",
    ):
        assert token in spec
    assert "Payload length: 4 bytes" in spec

    for token in (
        "test_smoke_commissioning_detects_heartbeat_echo_and_latency",
        "test_production_observer_reports_per_device_diagnostics",
        "test_specific_device_error_fails_commissioning",
        "test_sequence_gap_and_duplicate_fail_link_integrity",
    ):
        assert token in tests

    assert '"revision": "BREC-002"' in schema
    assert '"esp32_board_revision"' in schema

    print(
        "commissioning_contract_check PASS: raw ESP32 bridge, per-device STATUS diagnostics, "
        "sequence integrity, bench metadata, and cross-language masks aligned"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
