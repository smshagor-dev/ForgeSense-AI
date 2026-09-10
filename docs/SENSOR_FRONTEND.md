# Vendor-Neutral Sensor Frontend

## Purpose

ForgeSense keeps physical sensor bus/ADC drivers separate from the normalized safety and ML contract. This prevents a future component change from forcing a redesign of the FPGA safety state machine, ESP32 inference protocol, telemetry schema, or dashboard.

The frontend accepts driver-produced raw samples, applies deterministic calibration where required, converts conditioned vibration samples into a bounded RMS feature, and forwards normalized update strobes to the existing FPGA freshness/plausibility supervisor.

## Data path

```text
Physical sensor / ADC / digital bus
            |
      device-specific PHY
            |
       raw sample code
            |
   deterministic calibration
            |
  normalized channel update
            |
     sensor_supervisor
            |
 fresh + plausible + seen?
            |
      ForgeSense board core
```

For vibration the PHY is expected to provide a signed, conditioned acceleration sample in milli-g. The frontend computes a block RMS feature over a synthesis-time window. Gravity/DC removal, anti-alias filtering, sensor full-scale, and raw sample frequency belong to the device-specific acquisition driver and hardware profile.

## Linear calibration

Temperature and current use a deterministic integer transfer function. The current RTL boundary accepts signed 24-bit raw codes:

```text
normalized = ((raw - raw_zero) * gain_numerator) / gain_denominator + output_offset
```

Division truncates toward zero. The VHDL adapter and portable C++ reference use the same rule. The normalized numeric result saturates only at signed 16-bit representation limits; sensor-contract plausibility remains a separate check in `sensor_supervisor.vhd`.

This distinction matters: calibration saturation or a value outside the sensor contract must not be mistaken for a valid measurement simply because it was clamped into a machine-safety range.

## Vibration RMS

`vibration_rms_window.vhd` accumulates squared conditioned samples, divides by the configured window size, and applies an integer square root. It emits one `vibration_update` pulse per completed window.

The current implementation uses non-overlapping windows. Overlapping windows, spectral bands, crest factor, kurtosis, or FFT features can be added later without changing the normalized `milli_g_rms` interface.

## Current implementation

- `firmware/components/forgesense_sensing` — host-testable reference calibration and RMS math.
- `fpga/rtl/sensing/linear_sensor_adapter.vhd` — signed raw-code linear calibration.
- `fpga/rtl/sensing/vibration_rms_window.vhd` — fixed-window integer RMS.
- `fpga/rtl/sensing/sensor_frontend.vhd` — calibration/RMS composition.
- `fpga/rtl/top/forgesense_sensor_board_core.vhd` — frontend + freshness supervisor + existing board core integration.
- `fpga/tb/tb_sensor_frontend.vhd` — self-checking calibration/RMS testbench.

## What remains hardware-specific

No bus timing, I2C register map, 1-Wire transaction, SPI transaction, ADC reference voltage, shunt value, amplifier gain, accelerometer sensitivity, anti-alias network, or calibration coefficient is claimed final here. Those belong to the selected circuit revision and must be verified from component datasheets and measured hardware.
