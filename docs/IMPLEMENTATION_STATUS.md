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

Host-testable C++20 components implement protocol parsing, fixed-memory stream resynchronization, freshness gates, compact inference, CRC-protected event records, read-only device telemetry serialization, generated sensor-contract constants, and a vendor-neutral sensing math reference.

The sensing reference validates signed 24-bit raw codes, applies deterministic integer linear calibration, reports numeric saturation, and computes fixed-window vibration RMS with an integer square root.

### ESP32-S3 application and local monitor

`firmware/esp32` contains the edge runtime for FPGA UART transport, inference, sparse NVS events, and read-only `@FS1` host telemetry. The PC-side bridge feeds the local monitoring API/dashboard while preserving FPGA status authority and stale-source semantics. No actuator/control HTTP route is exposed.

The complete ESP-IDF target build still requires validation on the selected physical ESP32-S3 board.

### FPGA sensing and board integration

The VHDL tree contains deterministic safety/control, protocol RX/TX, UART, sample/timebase logic, generated sensor contract constants, and sensor freshness supervision.

The vendor-neutral frontend now adds:

- signed raw-code linear calibration for temperature and current;
- fixed-window integer vibration RMS extraction from conditioned milli-g samples;
- explicit normalized update strobes;
- numeric-saturation diagnostics;
- a `forgesense_sensor_board_core` wrapper connecting the frontend through `sensor_supervisor` into the existing board core.

Exact I2C/1-Wire/SPI/ADC transactions, analog transfer functions, accelerometer bias removal, anti-alias filtering, and final calibration coefficients remain device-specific and intentionally unfrozen until the physical BOM/schematic is selected.

The FPGA becomes operational only after accepted intelligence and valid sensor conditions satisfy the existing safety policy. Missing, stale, implausible, replayed, incompatible, or corrupt information cannot silently clear safety state.

## Current validation baseline

Existing repository validation covers Python simulation/integration, portable C++ protocol/stream/inference/event/telemetry/sensor-contract checks, and self-checking VHDL testbenches. The newly added portable sensing reference passes strict host compilation with `-Wall -Wextra -Werror -pedantic`.

The deterministic seven-scenario software matrix continues to cover normal operation, bearing degradation, overcurrent trend, cooling loss, sensor dropout, intelligence-link loss, and emergency input.

## Evidence still missing

The following remain intentionally unclaimed until measured:

- selected physical sensor accuracy and calibration;
- ADC/reference/shunt/amplifier transfer accuracy;
- accelerometer mounting and vibration bandwidth;
- electrical noise immunity and anti-alias performance;
- real motor/pump fault signatures and predictive lead time;
- false alarms per operating hour;
- ESP32-S3 device-level latency and memory use;
- UART/USB signal integrity on the selected boards;
- FPGA synthesis utilization and timing closure for the frontend arithmetic;
- power-tree, protection and output-driver validation;
- PCB manufacturing evidence;
- industrial functional-safety suitability or certification.
