from __future__ import annotations

import json
import math
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    profile = json.loads((root / "hardware/profiles/reference_circuit_v1.json").read_text())
    assert profile["schema"] == "forgesense.reference_circuit.v1"

    current = profile["current_sense"]
    motor = profile["motor"]
    i_ref = float(motor["reference_continuous_a"])
    shunt = float(current["shunt_ohm"])
    gain = float(current["gain"])
    adc_fs = float(current["adc_full_scale_v"])
    trip_ref = float(current["backup_trip_reference_v"])

    shunt_v = i_ref * shunt
    adc_v = shunt_v * gain
    shunt_power = i_ref * i_ref * shunt
    trip_a = trip_ref / (shunt * gain)
    cutoff_hz = 1.0 / (2.0 * math.pi * float(current["filter_r_ohm"]) * float(current["filter_c_f"]))

    assert 0.0 < shunt_v < 0.25
    assert 0.0 < adc_v < adc_fs
    assert float(current["shunt_min_power_w"]) >= 2.0 * shunt_power
    assert trip_a > i_ref
    assert trip_a < float(motor["fuse_a"])
    assert float(motor["mosfet_min_vds_v"]) >= 3.0 * float(profile["nominal_input_v"])
    assert 1000.0 < cutoff_hz < 2500.0
    assert motor["flyback_required"] is True
    assert motor["estop_hardware_gate_inhibit"] is True

    print(f"reference_circuit_check PASS: shunt={shunt_v:.3f} V, adc={adc_v:.3f} V, shunt_power={shunt_power:.3f} W, backup_trip={trip_a:.2f} A, cutoff={cutoff_hz:.0f} Hz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
