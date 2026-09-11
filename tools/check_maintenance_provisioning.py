from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    maintenance_app = (root / "firmware/esp32_calibration_maintenance/main/app_main.cpp").read_text(encoding="utf-8")
    maintenance_cmake = (root / "firmware/esp32_calibration_maintenance/main/CMakeLists.txt").read_text(encoding="utf-8")
    maintenance_kconfig = (root / "firmware/esp32_calibration_maintenance/main/Kconfig.projbuild").read_text(encoding="utf-8")
    maintenance_store = (root / "firmware/esp32_calibration_maintenance/main/calibration_store_nvs.cpp").read_text(encoding="utf-8")
    maintenance_protocol = (root / "firmware/esp32_calibration_maintenance/main/maintenance_protocol.cpp").read_text(encoding="utf-8")
    host_protocol = (root / "commissioning/forgesense_commission/provisioning.py").read_text(encoding="utf-8")
    host_tool = (root / "tools/run_physical_calibration_provisioning.py").read_text(encoding="utf-8")
    production_app = (root / "firmware/esp32/main/app_main.cpp").read_text(encoding="utf-8")
    transparent_bridge = (root / "firmware/esp32_commissioning/main/app_main.cpp").read_text(encoding="utf-8")
    tests = (root / "tests/test_maintenance_provisioning.py").read_text(encoding="utf-8")
    host_test = (root / "firmware/tests/maintenance_protocol_test.cpp").read_text(encoding="utf-8")

    for token in (
        'project(forgesense_calibration_maintenance)',
        '"maintenance_protocol.cpp"',
        '"calibration_store_nvs.cpp"',
        'forgesense_sensing',
    ):
        target_text = (root / "firmware/esp32_calibration_maintenance/CMakeLists.txt").read_text(encoding="utf-8") if token.startswith("project") else maintenance_cmake
        assert token in target_text, token

    assert maintenance_kconfig.count("default -1") >= 2
    for token in (
        "FORGESENSE_MAINTENANCE_ENABLE_GPIO",
        "FORGESENSE_LOAD_INHIBIT_SENSE_GPIO",
        "Physical maintenance-enable GPIO",
        "Physical load-inhibit sense GPIO",
    ):
        assert token in maintenance_kconfig, token

    for token in (
        "physical_gates_asserted()",
        "handle_prepare",
        "handle_commit",
        "g_boot_nonce",
        "g_commit_nonce",
        "g_pending_expected_floor",
        "stage_and_commit(g_pending_record)",
        "active_blob != g_pending_blob",
        "g_store_ready = false",
        "esp_efuse_mac_get_default",
        "nvs_flash_init()",
    ):
        assert token in maintenance_app, token
    assert maintenance_app.count("if (!physical_gates_asserted())") >= 2

    for forbidden in (
        "nvs_flash_erase",
        "uart_write_bytes",
        "uart_read_bytes",
        "UART_NUM_1",
        "load_enable",
        "set_hard_limit",
        "update_safety_limit",
        "http_post",
        "dashboard",
    ):
        assert forbidden.lower() not in maintenance_app.lower(), forbidden

    for token in (
        'kNamespace = "fs_cal"',
        'kSlotKeys[2]',
        'select_calibration_slot',
        'nvs_set_blob',
        'readback != encoded',
        'write_metadata(inactive_slot, candidate.sequence)',
    ):
        assert token in maintenance_store, token
    assert "nvs_flash_erase" not in maintenance_store

    for token in (
        "0xEDB88320U",
        "kMaintenanceMagic",
        "claimed_crc != computed_crc",
        "payload_size > kMaintenanceMaxPayload",
    ):
        assert token in maintenance_protocol, token

    for token in (
        'PHYSICAL_EVIDENCE_SCHEMA = "forgesense.calibration_physical_provisioning.v1"',
        'device_id=f"esp32s3:{mac_hex}"',
        "both physical maintenance and load-inhibit gates must be asserted",
        "client.prepare_record(",
        "client.commit_record(",
        "post.installed_sequence != candidate_sequence",
        "boot nonce did not change",
        '"may_relax_hard_safety_limits": False',
        '"hardware_backed_monotonic_counter_claimed": False',
    ):
        assert token in host_protocol, token

    verify_position = host_tool.index("verification = _verify_package(args)")
    serial_position = host_tool.index("serial_port = _serial_port")
    assert verify_position < serial_position
    assert 'WRITE_CONFIRMATION = "CALIBRATION-WRITE"' in host_tool
    assert "verify_provisioning_bundle(" in host_tool
    assert "if args.confirm_write != WRITE_CONFIRMATION" in host_tool

    for forbidden in (
        "stage_and_commit",
        "PrepareRecord",
        "CommitRecord",
        "fs_cal",
        "CALIBRATION-WRITE",
    ):
        assert forbidden not in production_app, f"production runtime gained maintenance write token: {forbidden}"
        assert forbidden not in transparent_bridge, f"transparent commissioning bridge gained maintenance write token: {forbidden}"

    for token in (
        "test_frame_parser_handles_fragmentation_crc_corruption_and_resync",
        "test_wrong_device_blocks_before_prepare",
        "test_open_physical_gate_blocks_before_prepare",
        "test_installed_sequence_mismatch_blocks_before_prepare",
        "test_commit_requires_matching_challenge",
        "test_post_write_readback_mismatch_fails",
        "test_reboot_verification_requires_new_boot_and_retained_record",
        "test_reboot_verification_rejects_same_boot",
    ):
        assert token in tests, token
    assert "maintenance_protocol_test PASS" in host_test

    print(
        "maintenance_provisioning_check PASS: dedicated default-disabled maintenance image, dual physical gates, "
        "two-step challenged commit, full host evidence verification, retained readback/reboot checks, and no "
        "production/transparent-bridge write authority are present"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
