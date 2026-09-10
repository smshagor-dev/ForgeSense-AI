from __future__ import annotations

import json
import math
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    profile = json.loads((root / "hardware/profiles/reference_circuit_v1.json").read_text(encoding="utf-8"))
    assert profile["schema"] == "forgesense.reference_circuit.v1"
    assert profile["revision"] == "RC-003"

    current = profile["current_sense"]
    motor = profile["motor"]
    i_ref = float(motor["reference_continuous_a"])
    shunt = float(current["shunt_ohm"])
    gain = float(current["gain"])
    shunt_v = i_ref * shunt
    adc_v = shunt_v * gain
    shunt_power = i_ref * i_ref * shunt
    fsr = float(current["adc_differential_full_scale_v"])
    utilization = adc_v / fsr
    trip_ref = float(current["comparator_supply_v"]) * float(current["trip_divider_bottom_ohm"]) / (float(current["trip_divider_top_ohm"]) + float(current["trip_divider_bottom_ohm"]))
    trip_a = trip_ref / (shunt * gain)
    cutoff_hz = 1.0 / (2.0 * math.pi * float(current["filter_r_ohm"]) * float(current["filter_c_f"]))

    assert math.isclose(shunt_v, 0.048, abs_tol=1e-12)
    assert math.isclose(adc_v, 0.96, abs_tol=1e-12)
    assert utilization <= float(current["reference_fsr_utilization_max"]) + 1e-12
    assert float(current["shunt_min_power_w"]) >= 3.0 * shunt_power
    assert 3.44 < trip_a < 3.50 < float(motor["fuse_a"])
    assert 1000.0 < cutoff_hz < 2500.0
    assert float(motor["mosfet_vds_v"]) >= 5.0 * float(profile["nominal_input_v"])
    assert motor["estop_hardware_gate_inhibit"] is True

    print(
        "reference_circuit_check PASS: "
        f"shunt={shunt_v:.3f} V, adc={adc_v:.3f} V ({utilization*100:.1f}% FSR), "
        f"shunt_power={shunt_power:.3f} W, trip={trip_a:.3f} A, cutoff={cutoff_hz:.0f} Hz"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
