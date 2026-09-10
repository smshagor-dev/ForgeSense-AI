# Low-Voltage Reference Circuits

## Scope

These circuits define a testable electrical starting point for the 12 V ForgeSense prototype. They are engineering references, not final certified hardware. Final resistor tolerances, semiconductor part numbers, thermal margins, creepage/clearance, PCB copper, EMC behavior, and machine-specific trip values require measured hardware evidence.

The machine-readable source is `hardware/profiles/reference_circuit_v1.json`.

## Power tree

```text
12 V input
  |
  +-- input fuse
  +-- reverse-polarity protection
  +-- transient suppression
  +-- bulk/local decoupling
  |
  +-- protected motor branch
  |
  +-- 5 V regulator
        |
        +-- 3.3 V regulator / board rail
              |
              +-- FPGA
              +-- ESP32-S3
              +-- sensors / ADC / logic
```

Motor switching current must not return through sensitive logic paths. Ground/current-return layout, shunt Kelvin routing, regulator placement, and decoupling are PCB design items, not merely schematic details.

## Current-sense reference

The concrete baseline now maps the earlier generic current-sense block to a 25 mOhm Kelvin shunt and an INA181A1-class 20 V/V current-sense amplifier. At the 3.2 A reference current this produces about 80 mV across the shunt and 1.60 V at the measurement output. Shunt dissipation is about 0.256 W, while the preliminary BOM keeps at least a 1 W requirement and prefers 2 W before measured thermal derating.

A 1 kOhm / 100 nF measurement filter gives an analytical cutoff near 1.59 kHz. A separate comparator-style backup reference near 1.73 V corresponds to about 3.46 A and remains independent of software inference.

The comparator output is represented in RTL as `analog_hard_trip` at `forgesense_phy_board_core`. It propagates through `external_hard_trip` into `safety_core`, joins the deterministic hard-critical path, disables the protected output, latches the FPGA fault state, and appears in FPGA status as hard-critical. It is not represented as an emergency input and is not sourced by the ESP32-S3.

The backup comparator is an additional protection path, not permission to weaken normalized FPGA hard limits.

## Precision acquisition baseline

The current hardware baseline uses ADS131M02 as the precision-ADC reference. It provides two simultaneously sampled 24-bit channels over SPI and supports programmable data rates up to 64 kSPS. The exact input network, reference/clock implementation, selected data rate, channel allocation, and anti-alias components still require graphical schematic capture and validation.

## Vibration and temperature baseline

ADXL355 is the low-noise digital vibration reference. SPI is preferred so the raw acceleration path remains isolated from the slower I2C temperature bus. The current software contract consumes conditioned milli-g samples and computes RMS windows downstream.

TMP117 is the digital temperature reference over I2C/SMBus. Its output must still pass the existing normalized range/freshness supervision before becoming safety-valid.

## Protected motor output

The motor-output reference uses a low-side N-channel MOSFET behavioral model with:

- minimum 40 V drain-source rating target for a 12 V prototype;
- 33 Ohm gate resistor;
- 100 kOhm gate pulldown;
- flyback path across the inductive load;
- hardware E-stop gate inhibit in addition to FPGA command logic;
- 5 A reference fuse target.

The final MOSFET must be specified for low RDS(on) at the actual available gate voltage, not merely at a 10 V datasheet condition. The final flyback/TVS network must be selected from measured motor current and transient energy.

## E-stop principle

The emergency input must have two effects in the final circuit:

1. enter the FPGA deterministic emergency/fault state; and
2. physically inhibit the output-driver gate/enable path.

This avoids relying on the edge processor or ML software to remove motor drive.

## Independent protection paths

The architecture distinguishes three separate intervention sources:

- normalized FPGA hard limits derived from validated temperature/vibration/current measurements;
- the independent analog comparator `external_hard_trip` path;
- the physical E-stop path.

ML remains predictive/advisory and cannot mask any of the three.

## SPICE references

- `hardware/circuits/current_sense_reference.cir`
- `hardware/circuits/motor_output_reference.cir`

The current-sense file is a behavioral mapping of the 25 mOhm / 20 V/V baseline, not a transistor-level vendor macro-model. The files still require execution in a SPICE simulator before SPICE evidence is claimed.

## Analytical check

Run:

```bash
python tools/check_reference_circuits.py
```

The check verifies current-sense headroom, shunt thermal margin, backup-trip ordering, MOSFET voltage-rating target, RC cutoff, flyback requirement, and hardware E-stop inhibit policy.
