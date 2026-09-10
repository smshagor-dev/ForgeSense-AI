# Hardware Baseline V1

## Purpose

This document turns the generic pre-hardware electronics model into a concrete but still revisable prototype baseline. It is not certification evidence and does not claim that unbuilt hardware has passed EMC, thermal, electrical-safety or functional-safety testing.

## Reference component set

- Tang Nano 9K / GW1NR-9 for deterministic FPGA logic. The board provides 8640 LUT4 resources, 468 Kbit block SRAM, two PLLs, 32 Mbit SPI flash and 2x24 header pads according to Sipeed documentation.
- ESP32-S3-DevKitC-1 for edge inference and telemetry. GPIO17 and GPIO18 are exposed as U1TXD/U1RXD on the board header and are reserved for the FPGA link.
- INA181A1 as the current-sense amplifier reference. The A1 option provides 20 V/V gain and the family supports a -0.2 V to 26 V common-mode range.
- ADS131M02 as the precision ADC reference: two simultaneously sampled 24-bit channels, SPI and programmable data rates up to 64 kSPS.
- ADXL355 as the vibration reference: low-noise digital three-axis accelerometer with SPI/I2C, integrated 20-bit conversion and selectable ±2/±4/±8 g ranges.
- TMP117 as the temperature reference: 16-bit I2C/SMBus device with -55 °C to 150 °C operating range and high specified accuracy.

The machine-readable record is `hardware/profiles/hardware_baseline_v1.json`; procurement substitutions must preserve the electrical/software contracts or explicitly revise them.

## Current measurement revision

The generic 50 mOhm / gain-10 behavioral path is refined to 25 mOhm plus 20 V/V. At 3.2 A:

- shunt voltage = 80 mV;
- amplified signal = 1.60 V;
- shunt dissipation = 0.256 W.

The existing 1.73 V independent comparator reference still corresponds to approximately 3.46 A. A preferred 2 W Kelvin shunt keeps substantial thermal margin, but final pulse/current derating still depends on the chosen part and PCB.

## Safety partition

The motor output can be removed by any of three independent FPGA/hardware paths: normalized hard limits, `ANALOG_HARD_TRIP`, or physical E-stop. ML may request bounded intervention but cannot mask these signals. The E-stop also has a physical gate-inhibit path outside clocked logic.

## Pin-freeze policy

The Tang Nano 9K 27 MHz clock is verified at FPGA pin 52. Other carrier I/O pins remain intentionally unfrozen until each external header position, FPGA bank voltage and onboard peripheral conflict is checked against the exact board revision. ESP32-S3 GPIO17/18 are documentation-verified for UART1 use but still require physical-board validation before a hardware-pass claim.

## Next schematic gate

Before PCB layout begins, the repository must contain a real KiCad schematic with ERC results, concrete regulator/comparator/MOSFET/passive part numbers, connector pinout, exact FPGA header mapping, ADC reference/clock network and an annotated current-return review.
