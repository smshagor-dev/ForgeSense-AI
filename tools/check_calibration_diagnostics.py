from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    tx = (root / "fpga/rtl/protocol/calibration_diag_tx.vhd").read_text(encoding="utf-8")
    top = (root / "fpga/rtl/top/forgesense_tang_nano_9k_calibration_top.vhd").read_text(encoding="utf-8")
    build = (root / "fpga/scripts/tang_nano_9k_calibration_build.tcl").read_text(encoding="utf-8")
    host = (root / "commissioning/forgesense_commission/calibration.py").read_text(encoding="utf-8")
    cli = (root / "commissioning/forgesense_commission/cli.py").read_text(encoding="utf-8")
    tests = (root / "tests/test_calibration_diagnostics.py").read_text(encoding="utf-8")
    vhdl_test = (root / "fpga/tb/tb_calibration_diag_tx.vhd").read_text(encoding="utf-8")

    for token in (
        'when 3 => byte_i <= x"32";',
        'when 6 => byte_i <= x"10";',
        "ads_ch0_raw",
        "ads_ch1_raw",
        "tmp_deci_c",
        "adxl_x_milli_g",
        "adxl_y_milli_g",
        "adxl_z_milli_g",
        "diagnostic_flags",
        "crc16_next",
    ):
        assert token in tx, token

    assert "load_enable_o <= '0';" in top
    assert "entity work.tmp117_controller" in top
    assert "entity work.adxl355_controller" in top
    assert "entity work.ads131m02_controller" in top
    assert "entity work.calibration_diag_tx" in top
    assert "entity work.uart_rx" not in top

    for forbidden in (
        "load_enable_o <= '1'",
        "recovery_sync",
        "safety_fsm",
        "intelligence_gate",
        "ml_observation",
    ):
        assert forbidden not in top.lower()

    assert "forgesense_tang_nano_9k_calibration_top" in build
    assert "calibration_diag_tx.vhd" in build
    assert "run all" in build

    for token in (
        "CALIBRATION_DIAGNOSTIC_MESSAGE_TYPE = 0x32",
        '"read_only": True',
        '"may_control_actuators": False',
        '"may_apply_calibration": False',
        '"may_relax_hard_safety_limits": False',
        '"forgesense.calibration_diagnostic_capture.v1"',
        "sequence_integrity_pass",
        "crc_or_frame_errors",
    ):
        assert token in host, token

    assert '"calibration"' in cli
    assert "capture_calibration_diagnostics" in cli
    assert "test_decode_calibration_diagnostic_preserves_signed_values" in tests
    assert "test_sequence_gap_blocks_capture_pass" in tests
    assert "test_device_error_marks_sample_unusable" in tests
    assert 'captured(3) = x"32"' in vhdl_test
    assert "crc16_next" in vhdl_test

    print("calibration_diagnostics_check PASS: read-only diagnostic framing, capture, safety boundary and regressions are present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
