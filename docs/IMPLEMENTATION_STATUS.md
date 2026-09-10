# Implementation Status

This document records what currently exists and what has executable evidence. It is intentionally more conservative than product-facing material.

## Executable now

### Deterministic virtual machine and sensors

`simulator/forgesense_sim` provides repeatable normal-operation, bearing-degradation, overcurrent, cooling-loss, and sensor-dropout traces. The simulator remains a pre-hardware reference and is not presented as a calibrated physical motor model.

### Reference model and deployment artifact

`ml/forgesense_ml/reference.py` defines one canonical training envelope: the complete settled normal trace after `STARTUP_SETTLE_SAMPLES = 80`. `fit_reference_model()` is reused by tests and demos to prevent different tools from silently fitting different baselines.

`ml/forgesense_ml/export_cpp.py` renders the same model as a deterministic C++ header committed at `firmware/components/forgesense_inference/include/forgesense_reference_model_generated.h`. A regression test compares regenerated output byte-for-byte with the committed artifact.

### Bidirectional FPGA/ESP32-S3 contract

ForgeSense Link v1 now has two implemented application messages:

- FPGA -> ESP32-S3 sensor snapshot (`0x11`, 22 bytes);
- ESP32-S3 -> FPGA ML observation (`0x10`, 28 bytes).

Both use explicit version/type/length fields, independent rolling sequence spaces, sender-local monotonic timestamps and CRC-16/CCITT-FALSE. The sensor message preserves signed temperature and per-channel validity. The intelligence message binds inference to model, model version and feature schema.

### Portable embedded runtime

Host-testable C++20 components implement:

- frame parsing and encoding;
- fixed-memory stream resynchronization;
- sequence freshness checks;
- fixed-size eight-sample feature window;
- the generated reference anomaly model;
- bounded ML observation production;
- 36-byte CRC32-protected event records.

These components compile with `-Wall -Wextra -Werror -pedantic` in the current host checks.

### ESP32-S3 application

`firmware/esp32` contains an ESP-IDF application scaffold. It configures UART, consumes the newest accepted sensor frame from each received chunk, rejects stale/duplicate sensor sequences, resets inference on invalid input or link loss, emits ML observations, and writes transition-oriented event records to an NVS ring.

The application intentionally has no actuator API. Its output toward the FPGA is a bounded intelligence observation, not a raw control command.

The complete ESP-IDF target build has not yet been validated against a selected physical ESP32-S3 board.

### FPGA sensing and board integration

The VHDL tree now contains:

- a configurable sample scheduler;
- FPGA-local millisecond timebase;
- 8N1 UART RX/TX;
- 22-byte sensor snapshot transmitter;
- 28-byte ML observation receiver;
- CRC validation;
- intelligence compatibility/freshness gate;
- persistent last-accepted health state;
- hard-limit monitor;
- supervised intelligence watchdog;
- deterministic safety state machine;
- platform-level and board-level integration cores.

The FPGA automatically becomes operational only after an accepted valid intelligence observation. Watchdog supervision is held inactive during warm-up. A first accepted critical observation transitions directly to shutdown so the protected output cannot be transiently enabled.

Accepted warning/critical state is retained between frames. A missing, corrupt, stale, incompatible, or replayed frame cannot clear the last accepted state and cannot reset the watchdog.

## Current validation baseline

Local reference verification currently includes:

- 11 Python regression tests;
- host C++ protocol test;
- host C++ stream/freshness test;
- host C++ inference test;
- host C++ event-record integrity test;
- deterministic seven-scenario validation matrix.

The validation matrix currently reports:

| Scenario | Expected behavior | Result |
| --- | --- | --- |
| Normal | no warning or terminal action | PASS |
| Bearing degradation | bounded ML shutdown after injection and before hard critical | PASS |
| Overcurrent trend | bounded ML shutdown after injection and before hard critical | PASS |
| Cooling loss | bounded ML shutdown after injection and before hard critical | PASS |
| Sensor dropout | deterministic immediate fault latch | PASS |
| Intelligence link loss | watchdog shutdown at defined timeout | PASS |
| Emergency | immediate fault latch | PASS |

The reference bearing run currently injects degradation at sample 220, first enters warning at 238 and reaches shutdown at 240 while the hard critical threshold remains false.

## Design defects closed by this implementation

Two integration defects were found through validation and corrected:

1. A previous closed-loop baseline was fitted to only a narrow subsection of normal settled operation. That could classify later normal thermal behavior as anomalous. The reference model is now fitted to the complete settled normal envelope and exported from one canonical function.
2. Accepted ML health was previously consumed as a transient frame pulse by the RTL state machine. The FPGA now retains the last accepted health state until a newer accepted frame replaces it. Startup critical intelligence also goes directly to shutdown without entering RUN.

## Evidence still missing

The following remain intentionally unclaimed until measured:

- physical sensor accuracy and calibration;
- electrical noise immunity;
- real motor/pump fault signatures;
- predictive lead time on real faults;
- false alarms per operating hour;
- ESP32-S3 device-level inference latency and memory use;
- UART signal integrity on the selected boards;
- FPGA synthesis utilization and timing closure;
- power-tree, protection and output-driver validation;
- PCB manufacturing evidence;
- industrial functional-safety suitability or certification.

### FPGA status feedback

The FPGA now emits `STATUS` (`0x30`) snapshots on the same outbound UART stream as sensor data. Status includes the actual deterministic state code, protected-output state, warning/fault/ready flags, hard-limit state, watchdog timeout, retained ML warning/critical state, emergency input, and required-sensor validity. A locked transmit arbiter prevents sensor/status bytes from interleaving.

The ESP32-S3 mixed stream decoder maintains independent sensor and status freshness gates and queues multiple fresh frames found in one UART read chunk, so status evidence is not lost merely because a sensor frame arrived in the same driver read.
