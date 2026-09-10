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

The development reference uses a 50 mΩ low-side shunt and gain of 10. At the existing 3.2 A reference critical region, this produces about 160 mV across the shunt and 1.60 V at the measurement output. The shunt dissipates about 0.512 W at 3.2 A, so the profile requires at least a 2 W shunt before further thermal derating.

A 1 kΩ / 100 nF measurement filter gives an analytical cutoff near 1.59 kHz. This filtered measurement feeds acquisition/ML. A separate comparator-style backup reference near 1.73 V corresponds to about 3.46 A and is intentionally independent of software inference.

The comparator output is now represented in RTL as `analog_hard_trip` at `forgesense_phy_board_core`. It propagates through `external_hard_trip` into `safety_core`, joins the deterministic hard-critical path, disables the protected output, latches the FPGA fault state, and appears in FPGA status as hard-critical. It is not represented as an emergency input and is not sourced by the ESP32-S3.

The backup comparator is an additional protection path, not permission to weaken normalized FPGA hard limits.

## Protected motor output

The motor-output reference uses a low-side N-channel MOSFET behavioral model with:

- minimum 40 V drain-source rating target for a 12 V prototype;
- 33 Ω gate resistor;
- 100 kΩ gate pulldown;
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

The current architecture therefore distinguishes three separate sources of intervention:

- normalized FPGA hard limits derived from validated temperature/vibration/current measurements;
- the independent analog comparator `external_hard_trip` path;
- the physical E-stop path.

ML remains predictive/advisory and cannot mask any of the three.

## SPICE references

- `hardware/circuits/current_sense_reference.cir`
- `hardware/circuits/motor_output_reference.cir`

The files use generic behavioral elements so topology and expected voltages can be checked before a specific amplifier/comparator/MOSFET is selected. They still require execution in a SPICE simulator before simulation evidence is claimed.

## Analytical check

Run:

```bash
python tools/check_reference_circuits.py
```

The check verifies current-sense headroom, shunt thermal margin, backup-trip ordering, MOSFET voltage-rating target, RC cutoff, flyback requirement, and hardware E-stop inhibit policy.
