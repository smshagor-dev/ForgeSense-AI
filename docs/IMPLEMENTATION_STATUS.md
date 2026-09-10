# Implementation Status

This document records what currently exists and what has executable evidence. It is intentionally more conservative than product-facing material.

## Executable now

### Deterministic virtual machine and sensors

`simulator/forgesense_sim` provides repeatable normal-operation, bearing-degradation, overcurrent, cooling-loss, and sensor-dropout traces. The simulator remains a pre-hardware reference and is not presented as a calibrated physical motor model.

### Reference model and deployment artifact

`ml/forgesense_ml/reference.py` defines one canonical training envelope: the complete settled normal trace after `STARTUP_SETTLE_SAMPLES = 80`. `fit_reference_model()` is reused by tests and demos to prevent tools from silently fitting different baselines.

`ml/forgesense_ml/export_cpp.py` renders the same model as a deterministic C++ header committed at `firmware/components/forgesense_inference/include/forgesense_reference_model_generated.h`. A regression test compares regenerated output byte-for-byte with the committed artifact.

### FPGA/ESP32-S3 application contract

ForgeSense Link v1 has three implemented application messages:

- FPGA -> ESP32-S3 sensor snapshot (`0x11`, 22 bytes);
- FPGA -> ESP32-S3 authoritative safety status (`0x30`, 18 bytes);
- ESP32-S3 -> FPGA ML observation (`0x10`, 28 bytes).

All frames use explicit version/type/length fields, independent rolling sequence spaces, sender-local monotonic timestamps, and CRC-16/CCITT-FALSE. FPGA status is the machine-state authority; ML observations cannot override hard safety.

### Portable embedded runtime

Host-testable C++20 components implement protocol parsing, fixed-memory stream resynchronization, freshness gates, compact inference, CRC-protected event records, read-only device telemetry serialization, generated sensor-contract constants, and sensing/PHY references.

The sensing path validates signed 24-bit raw codes, applies deterministic integer linear calibration, reports numeric saturation, and computes fixed-window vibration RMS with an integer square root.

The PHY reference provides a fixed 48-byte CRC32/IEEE calibration record, strict version/magic/size validation, raw ADC/current and normalized temperature boundaries, transport-error suppression, conditioned vibration processing, and explicit diagnostics.

Portable calibration and PHY tests are written for C++20 with `-Wall -Wextra -Werror -pedantic`.

### ESP32-S3 application and local monitor

`firmware/esp32` contains the edge runtime for FPGA UART transport, inference, sparse NVS events, and read-only `@FS1` host telemetry. The PC-side bridge feeds the local monitoring API/dashboard while preserving FPGA status authority and stale-source semantics. No actuator/control HTTP route is exposed.

The complete ESP-IDF target build still requires validation on the selected physical ESP32-S3 board.

### FPGA sensing and board integration

The VHDL tree contains deterministic safety/control, protocol RX/TX, UART, sample/timebase logic, generated sensor contract constants, and sensor freshness supervision.

The frontend includes signed raw-code calibration, fixed-window integer vibration RMS, normalized update strobes, numeric-saturation diagnostics, and `forgesense_sensor_board_core` connecting the frontend through `sensor_supervisor` into the board core.

The physical-interface reference adds `generic_adc_sample_adapter`, `digital_temperature_adapter`, `accelerometer_conditioner`, `sensor_self_test`, and `forgesense_phy_board_core`. The wrapper exposes both transport-level self-test and normalized `sensors_valid`; deterministic safety continues to rely on normalized freshness/plausibility rather than transport activity alone.

The component selection and electrical support networks are now defined, but device-specific ADS131M02/ADXL355/TMP117 register transactions and final FPGA application pin assignments are not yet implemented/frozen. The existing vendor-neutral sample interfaces remain the executable boundary until those device drivers are completed and tested.

### Calibration authority

`forgesense_calibration.*` defines an integrity-checked provisioning/reference record, but the current design exposes no dashboard or ESP32 runtime command that can rewrite FPGA safety calibration. FPGA coefficients remain frozen in the hardware build until a separately reviewed provisioning mechanism exists.

This preserves the rule that a compromised or malfunctioning monitoring/intelligence processor cannot relax measurement interpretation used by the deterministic safety boundary.

### Component-backed low-voltage hardware baseline

`hardware/profiles/hardware_baseline_v1.json` is now revision `HW-BL-003`. It links the protected power-entry, sensing-support, current-sense, motor-output, interconnect, package, and net-freeze sources used for schematic capture.

The 12 V input reference is:

```text
connector
  -> 5 A passive fuse
  -> SMBJ15A TVS
  -> TPS259470L eFuse
  -> VIN_12V_PROTECTED
```

The TPS259470L reference network produces approximately 9.03 V UVLO, 18.07 V OVLO, 4.04 A current limit, about 10.1 ms overcurrent blanking, and approximately 19.8 ms rise to 12 V. The intended current-intervention order is approximately 3.46 A analog motor hard trip, 4.04 A power-entry eFuse limit, then 5 A passive fuse.

The logic tree uses TPS54202DDCR for 5 V and TPS7A2033PDBVR for the quiet 3.3 V sensing rail.

The current measurement reference uses a 25 mOhm Kelvin shunt and INA181A1IDBVR at 20 V/V. At 3.2 A it produces 80 mV across the shunt, 1.60 V at `CS_OUT`, and approximately 0.256 W shunt dissipation. TLV3201AIDBVR compares `CS_OUT` against an approximately 1.729 V divider reference, corresponding to an ideal 3.46 A backup trip. Hysteresis remains DNI until measured switching-noise evidence exists.

UCC27511ADBVR drives CSD18540Q5B from 5 V. A normally-closed E-stop loop drives the driver's inverting input as a fail-high physical inhibit, while SN74LVC1G17DBVR exposes the state to the FPGA. STPS5L60U is the current flyback reference.

### Precision sensor support

`hardware/profiles/sensor_support_v1.json` defines the selected support networks without claiming physical performance:

- ADS131M02IPWR: 3.3 V AVDD/DVDD, 1 uF local rail decoupling, 220 nF CAP decoupling, internal reference, 8.192 MHz SiT8924 master clock, SPI and DRDY nets;
- ADXL355BEZ: 3.3 V supply/I/O, internal 1.8 V regulators, local bypass and discharge resistors, mode-0 SPI, 2 MHz starting clock, 1 kHz ForgeSense acquisition target, dedicated/gated SCLK requirement;
- TMP117AIDRVR: 3.3 V, 0.1 uF bypass, ADD0 to GND, 4.99 kOhm reference pull-ups for SCL/SDA/ALERT.

TMP117 ALERT remains diagnostic and does not replace the normalized FPGA temperature hard limit.

### Schematic-capture sources

The pre-layout electrical source set now includes:

- `hardware/profiles/power_entry_v1.json`;
- `hardware/profiles/sensor_support_v1.json`;
- `hardware/profiles/hardware_baseline_v1.json`;
- `hardware/profiles/reference_circuit_v1.json`;
- `hardware/profiles/interconnect_v1.json`;
- `hardware/kicad/schematic_contract_v1.json` (`SCH-CON-002`);
- `hardware/kicad/POWER_AND_SAFETY_SHEET_V1.md`;
- `hardware/kicad/component_packages_v1.csv`;
- `hardware/kicad/net_endpoints_v1.csv`;
- `hardware/bom/preliminary_bom_v1.csv`.

Manufacturer orderable MPN/package information is recorded separately from KiCad library footprint IDs. Footprint bindings remain intentionally pending until verified against the installed KiCad library. Tang Nano external application pins also remain intentionally unresolved rather than guessed.

### Hardware consistency checks

`make hardware-check` executes the cross-file hardware baseline checker and analytical circuit checker.

The hardware checker validates, among other things:

- eFuse UVLO/OVLO/current-limit/slew arithmetic;
- TVS/eFuse voltage coordination assumptions;
- analog-trip < eFuse < fuse ordering;
- current transfer and shunt thermal ratio;
- motor-driver/MOSFET/flyback reference constraints;
- E-stop fail-high hardware-inhibit policy;
- ADS131M02 clock/decoupling contract;
- ADXL355 SPI/discharge contract;
- TMP117 pull-up/bypass contract;
- BOM and package-manifest coverage;
- critical-net endpoint presence;
- continued absence of guessed FPGA application pins.

Behavioral SPICE files exist for the current-sense and inductive motor-output topologies. They remain source artifacts; no SPICE execution result is claimed until a compatible simulator is run and evidence is retained.

## Current validation baseline

Repository validation covers Python simulation/integration, portable C++ protocol/stream/inference/event/telemetry/sensor-contract/sensing/PHY checks, self-checking VHDL testbenches, hardware-profile consistency checks, and analytical low-voltage circuit checks.

Reference checks include calibration encode/decode and CRC-corruption rejection, invalid-calibration rejection, PHY normalization, deterministic 3 g / 4 g two-sample RMS = 3535 mg, signed 24-bit raw-range rejection, profile/schema consistency, protected-entry equations, current-sense calculations, and safety ordering.

The deterministic seven-scenario software matrix covers normal operation, bearing degradation, overcurrent trend, cooling loss, sensor dropout, intelligence-link loss, and emergency input.

## Evidence still missing

The following remain intentionally unclaimed until measured or tool-verified:

- selected physical sensor accuracy and calibration;
- ADS131M02 register-driver operation and measured ADC/reference/shunt/amplifier transfer accuracy;
- ADXL355 and TMP117 device-driver behavior on physical buses;
- actual shunt temperature rise and current-sense drift;
- comparator trip tolerance and chatter under motor switching noise;
- eFuse current-limit behavior, UVLO/OVLO tolerances, and real inrush waveform;
- measured flyback/TVS transient energy and clamp voltage;
- input surge/EMC qualification;
- selected MOSFET switching loss and junction temperature;
- accelerometer mounting and vibration bandwidth;
- electrical noise immunity and anti-alias performance;
- real motor/pump fault signatures and predictive lead time;
- false alarms per operating hour;
- ESP32-S3 device-level latency and memory use;
- UART/USB signal integrity on the selected boards;
- exact Tang Nano application-pin/CST mapping;
- FPGA synthesis utilization and timing closure for the complete physical acquisition path;
- power-tree efficiency and thermal performance;
- verified KiCad footprint binding, ERC/DRC, PCB manufacturing evidence;
- industrial functional-safety suitability or certification.
