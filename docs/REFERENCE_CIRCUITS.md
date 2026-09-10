# Low-Voltage Reference Circuits

## Scope

These circuits define the component-backed electrical starting point for the 12 V ForgeSense reference platform. They remain engineering references rather than certified hardware. Machine-specific limits, EMC, connector ratings, PCB thermal behavior, switching transients, and safety integrity require physical evidence.

Machine-readable sources:

- `hardware/profiles/reference_circuit_v1.json`
- `hardware/profiles/hardware_baseline_v1.json`
- `hardware/kicad/schematic_contract_v1.json`

## Power tree

```text
12 V input
  |
  +-- fuse / reverse-polarity / transient protection
  |
  +-- motor branch
  |
  +-- TPS54202 --> +5V_LOGIC
                       |
                       +-- Tang Nano 9K
                       +-- ESP32-S3 DevKit
                       +-- UCC27511A
                       |
                       +-- TPS7A2033 --> +3V3_QUIET
                                              |
                                              +-- INA181A1
                                              +-- ADS131M02
                                              +-- TLV3201
                                              +-- ADXL355
                                              +-- TMP117
```

TPS54202 is configured from TI's 5 V reference starting network: 15 uH, 10 uF + 0.1 uF input capacitance, 0.1 uF bootstrap, 2 × 22 uF output, 100 kOhm / 13.3 kOhm feedback, and 75 pF feed-forward.

## Current-sense reference

The reference uses a 25 mOhm Kelvin shunt and INA181A1 at gain 20 V/V.

At 3.2 A:

- shunt voltage: 80 mV;
- amplifier output: 1.60 V;
- shunt dissipation: 0.256 W.

The ADC path retains the 1 kOhm / 100 nF reference filter.

## Independent overcurrent backup

TLV3201 compares `CS_OUT` against a divider-generated reference. With 47.5 kOhm from 3.3 V to `CS_TRIP_REF` and 52.3 kOhm from the node to ground, the ideal reference is about 1.729 V. The resulting current threshold is about 3.46 A.

`ANALOG_HARD_TRIP` feeds the FPGA deterministic safety path. It is independent of ML and the ESP32-S3.

A hysteresis footprint is reserved but not populated until switching-noise measurements support a value.

## Gate drive and motor switch

UCC27511A runs from 5 V. The topology uses its two logic inputs as a hardware interlock:

```text
FPGA_LOAD_ENABLE ---------> IN+
ESTOP_INHIBIT_5V ---------> IN-
                               |
                               v
                         UCC27511A
                               |
                     22R on / 4.7R off
                               |
                               v
                        CSD18540Q5B
```

The driver output can be high only when `IN+` is high and `IN-` is low. That makes the inverting input suitable for a physical active-high inhibit.

CSD18540Q5B is a 60 V N-MOSFET with a maximum 3.3 mOhm RDS(on) specification at 4.5 V gate drive. A 100 kOhm gate pulldown keeps the switch off if drive is absent.

STPS5L60 is the 60 V, 5 A flyback reference.

## E-stop fail behavior

The E-stop loop is normally closed. Healthy wiring pulls `ESTOP_INHIBIT_5V` low. A pressed switch or cable-open condition leaves the 10 kOhm pull-up in control and drives the node high, disabling UCC27511A.

SN74LVC1G17 translates/conditions this 5 V inhibit node into a 3.3 V FPGA-readable signal. The output-disable path itself does not depend on the FPGA.

## SPICE references

- `hardware/circuits/current_sense_reference.cir`
- `hardware/circuits/motor_output_reference.cir`

They are behavioral verification inputs. A SPICE file in the repository is not simulation evidence until executed with a compatible simulator and retained with results.

## Analytical checks

Run:

```bash
make hardware-check
```

Checks include rail/component contracts, current transfer, shunt thermal ratio, divider threshold, backup-trip ordering, MOSFET/flyback voltage and current ratings, E-stop fail-high behavior, BOM coverage, and unresolved FPGA pin safeguards.
