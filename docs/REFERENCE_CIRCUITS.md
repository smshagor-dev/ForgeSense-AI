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
  +-- fuse / TVS / eFuse
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

## Current-sense reference

The selected front end uses a 15 mOhm Kelvin shunt and INA181A1 at gain 20 V/V.

At 3.2 A:

- shunt voltage: 48 mV;
- amplifier output: 0.960 V;
- shunt dissipation: about 0.154 W;
- ADS131M02 gain-1 positive full-scale utilization: 80% of the 1.2 V nominal differential range.

The ADC path retains the 1 kOhm / 100 nF reference filter.

## Independent overcurrent backup

TLV3201 compares `CS_OUT` against a divider-generated reference. With 23.2 kOhm from 3.3 V to `CS_TRIP_REF` and 10.7 kOhm from the node to ground, the ideal reference is about 1.042 V. The resulting current threshold is about 3.47 A.

`ANALOG_HARD_TRIP` feeds the FPGA deterministic safety path and remains independent of ML and ESP32-S3. A hysteresis footprint is reserved but not populated until switching-noise measurements support a value.

Reference intervention ordering is therefore:

```text
~3.47 A analog hard trip
< ~4.04 A eFuse input current limit
< 5 A passive fuse
```

## Gate drive and motor switch

UCC27511A runs from 5 V. `FPGA_LOAD_ENABLE` feeds `IN+`; `ESTOP_INHIBIT_5V` feeds `IN-`. CSD18540Q5B remains the 60 V N-MOSFET reference with 22 Ohm turn-on, 4.7 Ohm turn-off, and 100 kOhm gate pulldown. STPS5L60 is the 60 V / 5 A flyback reference.

## E-stop fail behavior

The E-stop loop is normally closed. Healthy wiring pulls `ESTOP_INHIBIT_5V` low. A pressed switch or cable-open condition leaves the 10 kOhm pull-up in control and drives the node high, disabling UCC27511A independently of FPGA clocked logic.

SN74LVC1G17 conditions the inhibit state into the 3.3 V FPGA observation domain without placing the hardware gate inhibit under FPGA control.

## Selected sensing devices

The reference measurement chain now has register-level FPGA support for:

- ADS131M02: 24-bit, 4-word frame, CPOL=0/CPHA=1, mandatory output CRC;
- ADXL355: SPI mode 0, identity/configuration readback, DRDY-driven three-axis burst;
- TMP117: I2C identity probe and signed temperature conversion.

These digital contracts do not constitute physical validation. Signal integrity, clock quality, noise, mounting, thermal lag, gain/offset, and interference still require bench evidence.

## SPICE references

- `hardware/circuits/current_sense_reference.cir`
- `hardware/circuits/motor_output_reference.cir`

They are behavioral verification inputs. A SPICE file in the repository is not simulation evidence until executed with a compatible simulator and retained with results.

## Analytical checks

Run:

```bash
make hardware-check
```

Checks include rail/component contracts, current transfer, ADC headroom, shunt thermal ratio, divider threshold, backup-trip ordering, selected-device register contracts, bus-rate direction, MOSFET/flyback ratings, E-stop fail-high behavior, BOM coverage, and unresolved FPGA pin safeguards.
