from __future__ import annotations

import json
from pathlib import Path


def test_sensor_phy_reference_profile() -> None:
    root = Path(__file__).resolve().parents[2]
    profile = json.loads((root / "hardware/profiles/sensor_phy_reference_v1.json").read_text())
    assert profile["schema"] == "forgesense.sensor_phy_reference.v1"
    assert profile["adc"]["raw_bits"] == 24
    assert profile["adc"]["signed"] is True
    assert profile["vibration"]["raw_sample_rate_hz"] > 10
    assert profile["vibration"]["rms_window_samples"] == 64
    assert profile["calibration"]["crc"] == "CRC32/IEEE"
    assert profile["calibration"]["policy"] == "invalid_or_corrupt_calibration_must_not_be_used"
