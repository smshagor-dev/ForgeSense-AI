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

    assert "safety_flags_i(7) <= device_identity_ok;" in platform
    assert "safety_flags_i(8) <= device_transport_error;" in platform
    assert "safety_flags_i(15 downto 9) <= (others => '0');" in platform

    for source in (board, sensor, phy):
        assert "device_identity_ok" in source
        assert "device_transport_error" in source
    assert "device_identity_i <= tmp_ok and adxl_ok and ads_ok;" in selected
    assert "device_transport_error_i <= tmp_error or adxl_error or ads_error;" in selected

    assert "SAFETY_DEVICE_IDENTITY_OK = 0x0080" in py_protocol
    assert "SAFETY_DEVICE_TRANSPORT_ERROR = 0x0100" in py_protocol
    assert "kSafetyDeviceIdentityOk = 0x0080" in cpp_protocol
    assert "kSafetyDeviceTransportError = 0x0100" in cpp_protocol
    assert "device_identity_ok()" in cpp_protocol
    assert "device_transport_error()" in cpp_protocol

    observe_start = core.index("def observe_production_stream")
    observe_end = core.index("def _find_check")
    observe_source = core[observe_start:observe_end]
    assert ".write(" not in observe_source, "production observation must remain read-only"
    assert "transport.write" in core, "smoke echo test must exercise TX"
    assert "observe_production_stream" in cli
    assert "run_smoke_commissioning" in cli
    assert "--record-out requires real metadata" in cli

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

    assert "0xC0, 0x00" in cpp_test
    assert "device_identity_ok()" in cpp_test
    assert "!parsed.status.device_transport_error()" in cpp_test

    assert "bit 7 selected-device identity/configuration OK" in spec
    assert "bit 8 selected-device transport error" in spec
    assert "Payload length: 4 bytes" in spec
    assert "diagnostic" in spec.lower()

    for token in (
        "test_smoke_commissioning_detects_heartbeat_and_echo",
        "test_smoke_record_only_marks_serial_evidence",
        "test_production_observer_reports_device_diagnostics",
        "test_production_observation_updates_record_without_inventing_manual_checks",
    ):
        assert token in tests

    print("commissioning_contract_check PASS: ESP32 raw bridge, read-only production observation, diagnostic STATUS bits, smoke evidence, and cross-language masks aligned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
