# Implementation Status

This document records what currently exists and what has executable or source-level evidence. It is intentionally more conservative than product-facing material.

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

The VHDL tree contains deterministic safety/control, protocol RX/TX, UART, sample/timebase logic, generated sensor contract constants, sensor freshness supervision, physical-interface adapters, selected-device acquisition controllers, and a Tang Nano 9K physical-board wrapper.

The normalized frontend includes signed raw-code calibration, fixed-window integer vibration RMS, normalized update strobes, numeric-saturation diagnostics, and `forgesense_sensor_board_core` connecting the frontend through `sensor_supervisor` into the board core.

The physical-interface reference adds `generic_adc_sample_adapter`, `digital_temperature_adapter`, `accelerometer_conditioner`, `sensor_self_test`, and `forgesense_phy_board_core`. The wrapper exposes both transport-level self-test and normalized `sensors_valid`; deterministic safety continues to rely on normalized freshness/plausibility rather than transport activity alone.

Selected register-level acquisition now exists for:

- TMP117 over I2C with Device ID verification, repeated-start temperature reads, ACK/NACK handling, and signed temperature conversion;
- ADXL355 over SPI mode 0 with identity checks, FILTER/RANGE/POWER_CTL programming and readback, DRDY-driven X/Y/Z burst acquisition, and fixed-point milli-g conversion;
- ADS131M02 over CPOL=0/CPHA=1 SPI with delayed RREG response handling, CLOCK programming/readback, 24-bit four-word conversion frames, and mandatory output CRC validation.

`forgesense_reference_sensor_io.vhd` composes the three selected devices with the existing normalized sensing and deterministic safety path.

`forgesense_tang_nano_9k_top.vhd` now binds that composition to the 27 MHz Tang Nano 9K physical interface, implements open-drain TMP117 I2C pins, synchronizes the asynchronous hard-trip/E-stop/recovery observations, and preserves the independent physical E-stop gate-inhibit authority.

### Selected sensor behavioral verification

Bus-level device models now exist under `fpga/tb/models/` for TMP117, ADXL355, and ADS131M02. They connect to the same I2C/SPI pins as the controller RTL and provide deterministic normal data plus fault injection.

Coverage includes:

- TMP117 valid identity/temperature, forced NACK, and wrong identity;
- ADXL355 valid configuration/sample burst, wrong identity, and corrupted configuration readback;
- ADS131M02 valid startup/sample frames, wrong identity, corrupted CLOCK readback, and corrupted output CRC;
- a combined selected-sensor acquisition-cluster test in which all three devices reach trusted configuration state and publish deterministic measurements.

`tools/check_sensor_behavioral_verification.py` enforces the expected model/test inventory and critical assertions. `.github/workflows/sensor-behavioral.yml` is configured to analyze and run the four self-checking GHDL suites when a hosted runner is allocated.

These models are verification sources, not physical-device evidence.

### Tang Nano 9K physical mapping

`hardware/profiles/interconnect_v1.json` revision `INT-002`, `fpga/constraints/tang_nano_9k.cst`, and `fpga/constraints/tang_nano_9k.sdc` now freeze the development-board application mapping against the official Sipeed schematic/pin map.

The external ForgeSense wiring uses J5-5 through J5-22 on 3.3 V banks for UART, hard-trip/E-stop/load control, TMP117 I2C, ADXL355 SPI/DRDY, and ADS131M02 SPI/DRDY. The map intentionally excludes:

- populated TF-card FPGA pins 36-39;
- onboard BL702 USB-UART FPGA pins 17/18;
- external BANK3 1.8 V FPGA pins 79-86.

The onboard 27 MHz oscillator remains FPGA pin 52. Onboard S2 is FPGA pin 4 in the 1.8 V bank and is used only as the local reset input.

`tools/check_tang_nano_9k_pinmap.py` verifies unique pin allocation, voltage standards, reserved-pin exclusion, the machine-readable interconnect profile, open-drain I2C behavior, and physical-top synchronizer invariants. `make tang-pin-check` runs this contract directly; `make hardware-check` includes it.

`fpga/scripts/tang_nano_9k_build.tcl` is the Gowin command-line project entry point and targets `GW1NR-LV9QN88PC6/I5` with `forgesense_tang_nano_9k_top`. A successful Gowin synthesis/place-and-route result is still pending.

### Calibration authority

`forgesense_calibration.*` defines an integrity-checked provisioning/reference record, but the current design exposes no dashboard or ESP32 runtime command that can rewrite FPGA safety calibration. FPGA coefficients remain frozen in the hardware build until a separately reviewed provisioning mechanism exists.

This preserves the rule that a compromised or malfunctioning monitoring/intelligence processor cannot relax measurement interpretation used by the deterministic safety boundary.

### Calibration evidence and repeated-run review

`tools/capture_calibration.py` converts hashed bench evidence into review-only `forgesense.calibration_proposal.v1` artifacts for current, temperature, and stationary accelerometer characterization. The capture path now retains declared expanded reference uncertainty (`k=2`) and per-axis accelerometer standard deviation in proposal provenance.

`tools/review_calibration.py` compares repeated proposals under `hardware/calibration/calibration_review_policy_v1.json`. The default policy requires at least three runs from consistent board revisions and repository commit, then checks current gain/intercept spread, temperature offset spread, accelerometer bias/noise spread, declared reference-uncertainty limits, and proposal quality.

The review emits `forgesense.calibration_review.v1`, including canonical source-proposal hashes and conservative engineering uncertainty proxies. Its authority is deliberately constrained: reviewer approval and a source-controlled change are required; automatic runtime application is forbidden; deterministic hard-safety limits cannot be relaxed by the review result.

Legacy proposals without the new accelerometer standard-deviation evidence fail review readiness cleanly rather than producing a runtime exception. `make calibration-check` covers the single-run capture path, repeated-run review behavior, evidence completeness, and source-level authority invariants.

These checks establish evidence-handling behavior only. No physical calibration accuracy, traceability, or production metrology claim is made until actual bench measurements are retained and reviewed.

### Component-backed low-voltage hardware baseline

`hardware/profiles/hardware_baseline_v1.json` is revision `HW-BL-004`. It links the protected power-entry, sensing-support, selected-device, current-sense, motor-output, interconnect, package, and net-freeze sources used for schematic capture. Its status now records the frozen Tang Nano 9K application mapping while retaining the pre-hardware evidence boundary.

The 12 V input reference is:

```text
connector
  -> 5 A passive fuse
  -> SMBJ15A TVS
  -> TPS259470L eFuse
  -> VIN_12V_PROTECTED
```

The TPS259470L reference network produces approximately 9.03 V UVLO, 18.07 V OVLO, 4.04 A current limit, about 10.1 ms overcurrent blanking, and approximately 19.8 ms rise to 12 V.

The intended protection ordering is:

```text
~3.47 A independent analog motor hard trip
< ~4.04 A power-entry eFuse reference limit
< 5 A passive fuse
```

The logic tree uses TPS54202DDCR for 5 V and TPS7A2033PDBVR for the quiet 3.3 V sensing rail.

The current measurement reference uses a 15 mOhm Kelvin shunt and INA181A1IDBVR at 20 V/V. At 3.2 A it produces 48 mV across the shunt and 0.960 V at `CS_OUT`, which is 80% of the selected ADS131M02 gain-1 positive differential full-scale reference. Shunt dissipation at that reference point is approximately 0.154 W.

TLV3201AIDBVR compares `CS_OUT` against an approximately 1.042 V divider reference, corresponding to an ideal analog backup trip near 3.47 A. Hysteresis remains DNI until measured switching-noise evidence exists.

UCC27511ADBVR drives CSD18540Q5B from 5 V. A normally-closed E-stop loop drives the driver's inverting input as a fail-high physical inhibit, while SN74LVC1G17DBVR exposes the state to the FPGA. STPS5L60U is the current flyback reference.

### Precision sensor support

`hardware/profiles/sensor_support_v1.json` and `hardware/profiles/sensor_devices_v1.json` define the selected support and register-level contracts without claiming physical performance:

- ADS131M02IPWR: 3.3 V AVDD/DVDD, local decoupling, internal reference, 8.192 MHz master clock, CPOL=0/CPHA=1 FPGA transport, 24-bit words, selected 1 kSPS configuration, output CRC required;
- ADXL355BEZ: 3.3 V supply/I/O, local bypass/discharge network, SPI mode 0, 2 MHz starting clock, selected 1 kHz output-data rate, +/-8 g range, identity and configuration readback checks;
- TMP117AIDRVR: 3.3 V, 0.1 uF bypass, ADD0 to GND, 4.99 kOhm reference pull-ups, Device ID `0x0117`, repeated-start two-byte temperature read.

TMP117 ALERT remains diagnostic and does not replace the normalized FPGA temperature hard limit.

### Schematic-capture sources

The pre-layout electrical source set includes:

- `hardware/profiles/power_entry_v1.json`;
- `hardware/profiles/sensor_support_v1.json`;
- `hardware/profiles/sensor_devices_v1.json`;
- `hardware/profiles/hardware_baseline_v1.json`;
- `hardware/profiles/reference_circuit_v1.json`;
- `hardware/profiles/interconnect_v1.json` revision `INT-002`;
- `hardware/kicad/schematic_contract_v1.json`;
- `hardware/kicad/POWER_AND_SAFETY_SHEET_V1.md`;
- `hardware/kicad/component_packages_v1.csv`;
- `hardware/kicad/net_endpoints_v1.csv`;
- `hardware/bom/preliminary_bom_v1.csv`;
- `fpga/constraints/tang_nano_9k.cst`;
- `fpga/constraints/tang_nano_9k.sdc`.

Manufacturer orderable MPN/package information is recorded separately from KiCad library footprint IDs. Footprint bindings remain intentionally pending until verified against the installed KiCad library.

### Hardware consistency checks

`make hardware-check` validates the cross-file hardware baseline, analytical circuit calculations, selected sensor register/transport contracts, frozen Tang Nano 9K pin mapping, and calibration review-source contracts.

Checks include:

- eFuse UVLO/OVLO/current-limit/slew arithmetic;
- TVS/eFuse voltage coordination assumptions;
- analog-trip < eFuse < fuse ordering;
- revised 15 mOhm current transfer and ADC headroom;
- motor-driver/MOSFET/flyback reference constraints;
- E-stop fail-high hardware-inhibit policy;
- ADS131M02 clock, framing, CRC, and selected register contract;
- ADXL355 selected identities/register configuration;
- TMP117 address/identity/temperature-register contract;
- BOM and package-manifest coverage;
- critical-net endpoint presence;
- frozen Tang Nano J5 pin allocation and reserved-interface exclusions;
- LVCMOS33/LVCMOS18 voltage-standard consistency;
- 27 MHz timing constraint and physical-top open-drain/synchronizer invariants;
- calibration review-only authority, uncertainty, repeatability, and evidence-completeness contracts.

Behavioral SPICE files exist for the current-sense and inductive motor-output topologies. They remain source artifacts; no SPICE execution result is claimed until a compatible simulator is run and evidence is retained.

## Current validation baseline

Repository validation covers Python simulation/integration, portable C++ protocol/stream/inference/event/telemetry/sensor-contract/sensing/PHY checks, hardware-profile consistency checks, analytical low-voltage circuit checks, static physical-pin consistency, calibration evidence/review checks, and a growing set of self-checking VHDL verification sources.

Reference software checks include calibration encode/decode and CRC-corruption rejection, invalid-calibration rejection, PHY normalization, deterministic 3 g / 4 g two-sample RMS = 3535 mg, signed 24-bit raw-range rejection, profile/schema consistency, protected-entry equations, current-sense calculations, safety ordering, and repeated-run calibration rejection behavior.

The deterministic seven-scenario software matrix covers normal operation, bearing degradation, overcurrent trend, cooling loss, sensor dropout, intelligence-link loss, and emergency input.

The selected sensor behavioral suite and Tang Nano physical-top analysis are wired for GHDL execution. Local GHDL execution is not claimed in the current development environment, and recent hosted runs have historically stopped before job-step allocation. A passing hosted or retained local GHDL run is therefore still required before reporting compiler/simulation success for those VHDL additions.

## Evidence still missing

The following remain intentionally unclaimed until measured or tool-verified:

- a retained successful GHDL compile/run for the selected-device bus models and Tang Nano physical top;
- successful Gowin synthesis, place-and-route, resource-utilization report, and timing closure for the physical top;
- physical continuity confirmation for the frozen J5 wiring on the actual board revision;
- three or more retained physical calibration runs with defensible reference-instrument uncertainty and a passing repeated-run review;
- selected physical sensor accuracy and calibration;
- ADS131M02 behavior on the physical bus and measured ADC/reference/shunt/amplifier transfer accuracy;
- ADXL355 and TMP117 behavior on physical buses;
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
- UART/SPI/I2C signal integrity and I2C rise-time on the selected boards;
- power-tree efficiency and thermal performance;
- verified KiCad footprint binding, ERC/DRC, PCB manufacturing evidence;
- industrial functional-safety suitability or certification.
