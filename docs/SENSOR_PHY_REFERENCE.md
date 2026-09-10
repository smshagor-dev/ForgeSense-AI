# Sensor PHY and Electronics Reference

## Purpose

ForgeSense keeps device-specific buses and analog transfer functions below a vendor-neutral sensor PHY boundary. This allows the safety, telemetry, and ML stack to remain stable while the physical temperature sensor, current-sense circuit, ADC, or accelerometer changes.

The reference profile is `hardware/profiles/sensor_phy_reference_v1.json`.

## Boundary

```text
Physical sensor / analog front-end
        ↓
Device driver / ADC transport
        ↓
PHY sample + error indication
        ↓
Conditioning / calibration / RMS
        ↓
Normalized sensor frontend
        ↓
Freshness + plausibility supervisor
        ↓
FPGA safety / telemetry
```

No transport error is allowed to create a normalized update pulse. A failed or absent source therefore becomes stale at the supervisor instead of silently reusing an old sample forever.

## Temperature

The reference accepts a digital temperature source already converted to signed deci-degrees Celsius. The adapter rejects transport-error samples. The normalized value can still pass through the existing linear correction stage using frozen coefficients. Exact bus, conversion timing, checksum behavior, and part number are not frozen yet.

## Current

The current reference accepts a signed 24-bit raw ADC code plus sample-valid and sample-error indications. Calibration maps the raw code into milliamps using deterministic integer math. The physical implementation still requires a selected shunt/Hall topology, gain or isolation stage where appropriate, ADC reference, common-mode limits, input protection, anti-alias filtering, and measured calibration points.

## Vibration

The accelerometer PHY accepts signed milli-g samples after device-level axis selection/bias handling. It rejects samples outside the configured absolute range before they enter the RMS accumulator. The reference profile uses 1 kHz raw vibration sampling and a 64-sample RMS window; these are interface defaults, not measured optimum values for a particular machine.

## Calibration record

`forgesense_calibration.*` defines a fixed 48-byte record containing magic/version, record sequence, temperature calibration, current calibration, and CRC32/IEEE. Bad magic, size, version, CRC, denominator, or signed-24-bit raw-zero causes rejection.

This record is a provisioning/reference artifact. The current system exposes no runtime command that lets the ESP32-S3 or dashboard alter FPGA safety calibration. Calibration used by the FPGA remains frozen in the hardware build until a separately reviewed provisioning mechanism exists.

## Sensor self-test

`sensor_self_test.vhd` tracks successful transport-level activity for each required channel. A pass requires recent temperature, current, and conditioned-vibration activity with no active transport fault. `sensor_supervisor.vhd` independently enforces normalized plausibility and freshness, so transport liveness cannot substitute for data validity.

`forgesense_phy_board_core.vhd` exposes both `phy_self_test_pass` and aggregate `sensors_valid`. Bring-up software should record both; the safety path continues to depend on normalized validity rather than diagnostic optimism.

## Simulation

```bash
make phy-sim
make firmware-host
```

Host C++ tests cover calibration integrity and vendor-neutral PHY behavior. VHDL tests cover ADC error propagation and accelerometer range rejection when a VHDL simulator is available.

## What remains physical

No claim is made yet for exact sensor/ADC selection, analog gain/tolerances, input protection effectiveness, anti-alias response, vibration axis/bias strategy, ADC noise-free resolution, current offset drift, thermal placement, calibrated uncertainty, or EMC/noise immunity.
