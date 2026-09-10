# Implementation Status

This document records what currently exists and what has executable evidence. It is intentionally more conservative than product-facing material.

## Executable now

### Deterministic virtual machine and sensors

`simulator/forgesense_sim` provides repeatable normal-operation, bearing-degradation, overcurrent, cooling-loss, and sensor-dropout traces. The simulator remains a pre-hardware reference and is not presented as a calibrated physical motor model.

### Reference model and deployment artifact

`ml/forgesense_ml/reference.py` defines one canonical training envelope: the complete settled normal trace after `STARTUP_SETTLE_SAMPLES = 80`. `fit_reference_model()` is reused by tests and demos to prevent different tools from silently fitting different baselines.

`ml/forgesense_ml/export_cpp.py` renders the same model as a deterministic C++ header committed at `firmware/components/forgesense_inference/include/forgesense_reference_model_generated.h`. A regression test compares regenerated output byte-for-byte with the committed artifact.

### FPGA/ESP32-S3 application contract

ForgeSense Link v1 has three implemented application messages:

- FPGA -> ESP32-S3 sensor snapshot (`0x11`, 22 bytes);
- FPGA -> ESP32-S3 authoritative safety status (`0x30`, 18 bytes);
- ESP32-S3 -> FPGA ML observation (`0x10`, 28 bytes).

All frames use explicit version/type/length fields, independent rolling sequence spaces, sender-local monotonic timestamps, and CRC-16/CCITT-FALSE. The FPGA status message is the machine-state authority; ML observations cannot override hard safety.

### Portable embedded runtime

Host-testable C++20 components implement protocol parsing, fixed-memory stream resynchronization, freshness gates, compact inference, CRC-protected event records, read-only device telemetry serialization, generated sensor-contract constants, and vendor-neutral sensing/PHY references.

The sensing path validates signed 24-bit raw codes, applies deterministic integer linear calibration, reports numeric saturation, and computes fixed-window vibration RMS with an integer square root.

The PHY reference additionally provides a fixed 48-byte CRC32/IEEE calibration record, strict version/magic/size validation, raw ADC/current and normalized temperature boundaries, transport-error suppression, conditioned vibration processing, and explicit diagnostics.

Portable calibration and PHY tests pass C++20 compilation with `-Wall -Wextra -Werror -pedantic`.

### ESP32-S3 application and local monitor

`firmware/esp32` contains the edge runtime for FPGA UART transport, inference, sparse NVS events, and read-only `@FS1` host telemetry. The PC-side bridge feeds the local monitoring API/dashboard while preserving FPGA status authority and stale-source semantics. No actuator/control HTTP route is exposed.

The complete ESP-IDF target build still requires validation on the selected physical ESP32-S3 board.

### FPGA sensing and board integration

The VHDL tree contains deterministic safety/control, protocol RX/TX, UART, sample/timebase logic, generated sensor contract constants, and sensor freshness supervision.

The vendor-neutral frontend includes signed raw-code calibration, fixed-window integer vibration RMS, normalized update strobes, numeric-saturation diagnostics, and `forgesense_sensor_board_core` connecting the frontend through `sensor_supervisor` into the existing board core.

The physical-interface reference adds `generic_adc_sample_adapter`, `digital_temperature_adapter`, `accelerometer_conditioner`, `sensor_self_test`, and `forgesense_phy_board_core`. The wrapper exposes both transport-level self-test and normalized `sensors_valid`; safety continues to rely on normalized freshness/plausibility rather than transport activity alone.

Exact I2C/1-Wire/SPI/ADC transactions, analog transfer functions, accelerometer bias removal, anti-alias filtering, and final calibration coefficients remain device-specific and intentionally unfrozen until the physical BOM/schematic is selected.

### Calibration authority

`forgesense_calibration.*` defines an integrity-checked provisioning/reference record, but the current design exposes no dashboard or ESP32 runtime command that can rewrite FPGA safety calibration. FPGA coefficients remain frozen in the hardware build until a separately reviewed provisioning mechanism exists.

This preserves the rule that a compromised or malfunctioning monitoring/intelligence processor cannot relax measurement interpretation used by the deterministic safety boundary.

### Low-voltage circuit reference

`hardware/profiles/reference_circuit_v1.json` and `docs/REFERENCE_CIRCUITS.md` now define a 12 V prototype electrical starting point. The reference includes a separated motor/logic power tree, input fuse/reverse-polarity/transient-protection requirements, a protected low-side MOSFET motor output, flyback requirement, hardware E-stop gate inhibit, and a low-side current-sense path.

The current-sense analytical reference uses a 50 mΩ shunt and gain of 10. At 3.2 A it produces 160 mV at the shunt and 1.60 V after gain, with about 0.512 W shunt dissipation. The profile requires at least a 2 W shunt before additional thermal derating. A 1 kΩ/100 nF filter gives about 1.59 kHz cutoff, and the independent backup threshold reference corresponds to about 3.46 A.

Behavioral SPICE files exist for the current-sense and inductive motor-output topologies. They are source artifacts only; no SPICE execution result is claimed until a simulator actually runs them.

`tools/check_reference_circuits.py` independently verifies analytical headroom, shunt thermal margin, backup-trip ordering, MOSFET voltage-rating target, RC cutoff, flyback requirement, and hardware E-stop inhibit policy.

## Current validation baseline

Existing repository validation covers Python simulation/integration, portable C++ protocol/stream/inference/event/telemetry/sensor-contract/sensing/PHY checks, and self-checking VHDL testbenches.

Reference checks now include calibration encode/decode and CRC-corruption rejection, invalid-calibration rejection, vendor-neutral PHY normalization, deterministic 3 g / 4 g two-sample RMS = 3535 mg, signed 24-bit raw-range rejection, profile-schema regression, and analytical low-voltage circuit checks.

The deterministic seven-scenario software matrix continues to cover normal operation, bearing degradation, overcurrent trend, cooling loss, sensor dropout, intelligence-link loss, and emergency input.

## Evidence still missing

The following remain intentionally unclaimed until measured:

- selected physical sensor accuracy and calibration;
- ADC/reference/shunt/amplifier transfer accuracy;
- actual shunt temperature rise and current-sense drift;
- selected MOSFET switching loss and junction temperature;
- measured flyback/TVS transient energy and clamp voltage;
- accelerometer mounting and vibration bandwidth;
- electrical noise immunity and anti-alias performance;
- real motor/pump fault signatures and predictive lead time;
- false alarms per operating hour;
- ESP32-S3 device-level latency and memory use;
- UART/USB signal integrity on the selected boards;
- FPGA synthesis utilization and timing closure for the frontend arithmetic;
- power-tree/regulator efficiency and protection validation;
- PCB manufacturing evidence;
- industrial functional-safety suitability or certification.
