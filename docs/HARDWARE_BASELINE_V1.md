# Hardware Baseline V1

## Purpose

`HW-BL-002` is the first component-backed schematic baseline for the ForgeSense low-voltage reference platform. It is detailed enough to drive schematic capture, BOM review, analytical checks, and later PCB layout, while deliberately leaving board-revision-dependent FPGA header assignments unresolved.

This is engineering reference material. It is not certification evidence and does not establish safe limits for an arbitrary motor or industrial machine.

## Compute

- FPGA: Sipeed Tang Nano 9K, GW1NR-9, 27 MHz onboard clock.
- Edge processor: ESP32-S3-DevKitC-1.
- FPGA/ESP32 transport: UART 115200 8N1.
- ESP32 GPIO17 is U1TXD and GPIO18 is U1RXD in the selected development-board profile.
- Tang Nano external application pins remain unfrozen until the exact board revision is verified.

## Power

The 12 V protected input is split into the motor branch and logic conversion.

### 5 V logic rail

TPS54202 is the reference 12 V to 5 V synchronous buck. The starting network follows TI's 5 V reference design:

- 15 uH inductor;
- 10 uF plus 0.1 uF input decoupling;
- 0.1 uF bootstrap capacitor;
- two 22 uF output capacitors;
- 100 kOhm / 13.3 kOhm feedback divider;
- 75 pF feed-forward capacitor;
- 2 A device output rating.

### 3.3 V quiet rail

TPS7A2033 creates `+3V3_QUIET` from 5 V for the precision sensing domain. The reference starts with 2.2 uF input and 2.2 uF output ceramics. The LDO is rated for 300 mA and requires at least 1 uF output capacitance.

The quiet rail does not carry motor or gate-driver current.

## Current sensing

The current path uses a 25 mOhm Kelvin shunt and INA181A1 at 20 V/V.

At the 3.2 A reference point:

```text
Vshunt = 3.2 A × 0.025 Ohm = 0.080 V
CS_OUT = 0.080 V × 20 = 1.600 V
Pshunt = 3.2² × 0.025 = 0.256 W
```

The BOM requires at least 1 W and preferably 2 W for the shunt before real thermal validation.

## Independent analog trip

TLV3201 is the reference comparator, powered from 3.3 V. A 47.5 kOhm / 52.3 kOhm 0.1% divider creates approximately 1.729 V. With the current transfer above, the ideal reference trip is approximately 3.46 A.

Comparator hysteresis is intentionally a DNI footprint until motor-switching noise is measured. The comparator output feeds the FPGA `external_hard_trip` path and is never routed through the ESP32-S3.

## Motor switch and physical E-stop

UCC27511A is the reference 5 V low-side gate driver. `IN+` receives the FPGA load command. `IN-` is the independent active-high hardware inhibit.

The E-stop is a normally-closed loop:

- healthy closed loop pulls `ESTOP_INHIBIT_5V` low;
- pressed switch or broken cable releases the node;
- a 10 kOhm pull-up drives it high;
- high `IN-` forces the gate driver output low.

The motor MOSFET is CSD18540Q5B, a 60 V logic-level N-channel device with RDS(on) specified at 4.5 V. Starting gate resistors are 22 Ohm turn-on and 4.7 Ohm turn-off, with a 100 kOhm gate-to-source pulldown.

STPS5L60 is the initial 60 V, 5 A flyback reference. Final thermal suitability depends on measured motor current and transient energy.

SN74LVC1G17, powered at 3.3 V, buffers the 5 V E-stop inhibit state into the FPGA sensing domain. The hardware gate inhibit itself remains independent of that buffer and FPGA clocking.

## Precision sensing

- ADS131M02: 24-bit, two-channel simultaneous-sampling delta-sigma ADC; SPI; 3.3 V analog/digital rail; internal reference.
- ADXL355: low-noise 20-bit digital accelerometer; SPI; ±8 g reference configuration; 1 kHz ForgeSense raw acquisition target.
- TMP117: 16-bit I2C temperature sensor; 3.3 V rail; 0.0078125 °C per LSB.

## Schematic source of truth

The following files must agree:

- `hardware/profiles/hardware_baseline_v1.json`
- `hardware/profiles/reference_circuit_v1.json`
- `hardware/kicad/schematic_contract_v1.json`
- `hardware/kicad/POWER_AND_SAFETY_SHEET_V1.md`
- `hardware/bom/preliminary_bom_v1.csv`

Run:

```bash
make hardware-check
```

The checker prevents silent drift between the hardware profile, schematic contract, BOM, current-transfer calculation, trip threshold, E-stop policy, and development-board UART mapping.
