from __future__ import annotations

import struct

from forgesense_commission.calibration import (
    CALIBRATION_DIAGNOSTIC_MESSAGE_TYPE,
    CAL_ALL_DEVICE_OK,
    CAL_ALL_SAMPLE_SEEN,
    CalibrationDiagnosticObserver,
    decode_calibration_diagnostic,
)
from forgesense_protocol import decode_frame, encode_frame


def _signed24_le(value: int) -> bytes:
    if not (-0x800000 <= value <= 0x7FFFFF):
        raise ValueError("signed24 out of range")
    if value < 0:
        value += 1 << 24
    return bytes((value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF))


def _frame(
    sequence: int,
    *,
    ads0: int = -123456,
    ads1: int = 654321,
    tmp_deci_c: int = 253,
    x_mg: int = -12,
    y_mg: int = 8,
    z_mg: int = 1005,
    flags: int = CAL_ALL_SAMPLE_SEEN | CAL_ALL_DEVICE_OK,
) -> bytes:
    payload = (
        _signed24_le(ads0)
        + _signed24_le(ads1)
        + struct.pack("<hhhH", tmp_deci_c, x_mg, y_mg, z_mg, flags)
    )
    return encode_frame(
        message_type=CALIBRATION_DIAGNOSTIC_MESSAGE_TYPE,
        sequence=sequence,
        timestamp_ms=1000 + sequence * 50,
        payload=payload,
    )


def test_decode_calibration_diagnostic_preserves_signed_values() -> None:
    sample = decode_calibration_diagnostic(decode_frame(_frame(7)))
    assert sample.sequence == 7
    assert sample.ads_ch0_raw == -123456
    assert sample.ads_ch1_raw == 654321
    assert sample.temperature_c == 25.3
    assert sample.adxl_x_milli_g == -12
    assert sample.adxl_z_milli_g == 1005
    assert sample.sample_set_complete is True
    assert sample.devices_trusted is True
    assert sample.usable_for_calibration is True


def test_observer_accepts_clean_sequence_and_exports_read_only_authority() -> None:
    observer = CalibrationDiagnosticObserver()
    observer.feed(_frame(10) + _frame(11) + _frame(12))
    result = observer.as_dict()
    assert observer.capture_pass is True
    assert result["frames"] == 3
    assert result["usable_samples"] == 3
    assert result["sequence_gaps"] == 0
    assert result["sequence_faults"] == 0
    assert result["authority"]["read_only"] is True
    assert result["authority"]["may_control_actuators"] is False
    assert result["authority"]["may_apply_calibration"] is False
    assert result["authority"]["may_relax_hard_safety_limits"] is False


def test_sequence_gap_blocks_capture_pass() -> None:
    observer = CalibrationDiagnosticObserver()
    observer.feed(_frame(1) + _frame(3))
    assert observer.sequence_gaps == 1
    assert observer.capture_pass is False


def test_device_error_marks_sample_unusable() -> None:
    observer = CalibrationDiagnosticObserver()
    observer.feed(_frame(1, flags=CAL_ALL_SAMPLE_SEEN | CAL_ALL_DEVICE_OK | 0x0040))
    assert observer.frames == 1
    assert len(observer.usable_samples) == 0
    assert observer.capture_pass is False


def test_duplicate_sequence_is_rejected_from_retained_samples() -> None:
    observer = CalibrationDiagnosticObserver()
    observer.feed(_frame(20) + _frame(20))
    assert observer.frames == 2
    assert observer.sequence_faults == 1
    assert len(observer.samples) == 1
    assert observer.capture_pass is False
