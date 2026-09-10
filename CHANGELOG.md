# Changelog

All notable repository-level changes are recorded here.

## Unreleased

### Added

- Component-backed `HW-BL-003` hardware baseline with TPS259470L protected 12 V entry, SMBJ15A TVS, explicit UVLO/OVLO, eFuse current limiting, slew control, and layered 3.46 A / 4.04 A / 5 A protection ordering.
- Precision sensing support contract for ADS131M02 decoupling and 8.192 MHz clocking, ADXL355 low-noise SPI/bypass behavior, and TMP117 I2C pull-ups/bypass.
- KiCad-preparation package/MPN manifest, net-endpoint/freeze table, and `SCH-CON-002` schematic contract without guessed FPGA application pins or unverified footprint identifiers.
- Expanded hardware consistency checker covering power-entry equations, TVS/eFuse coordination, sensor-support networks, BOM/package coverage, critical-net policy, and unresolved pin safeguards.
- Low-voltage 12 V power-tree, protected motor-output, current-sense, flyback, and hardware E-stop reference architecture.
- Machine-readable circuit profile plus analytical electrical checks for shunt headroom/thermal margin, backup-trip ordering, RC filtering, and MOSFET voltage-rating targets.
- Behavioral SPICE references for the current-sense path and protected inductive motor output.
- Vendor-neutral sensor PHY/electronics reference profile for signed 24-bit ADC samples, digital temperature, conditioned accelerometer data, and immutable safety-boundary calibration policy.
- Fixed-size CRC32/IEEE calibration record with version, sequence, temperature/current coefficients, and strict integrity validation.
- Portable C++ sensor PHY reference that suppresses invalid transport samples before normalized updates and produces windowed vibration RMS.
- FPGA generic ADC, digital temperature, accelerometer conditioning, and sensor self-test adapters plus a composed physical-board wrapper.
- Pre-hardware PHY simulation, host calibration/PHY regression tests, and VHDL adapter verification wiring.
- Fixed-memory ESP32-S3 device telemetry snapshot serializer using `forgesense.edge.telemetry.v1` and reserved `@FS1 ` console records.
- Read-only physical-device dashboard bridge with strict schema/range validation and stale-source preservation.
- Periodic ESP32 telemetry publisher with immediate records for important FPGA state and edge-health transitions.
- Machine-readable pre-hardware ESP32-S3 reference profile separating the FPGA UART from the host telemetry console.
- Cross-language C++ -> Python telemetry compatibility validation.
- Read-only local telemetry API with authoritative FPGA state, independent source freshness, bounded in-memory diagnostic transitions, and no control routes.
- Dependency-free local monitoring dashboard for deterministic state, sensors, edge anomaly information, and safety flags.
- Long-poll telemetry revision endpoint and regression coverage for authority, staleness, bounded events, and HTTP write rejection.
- FPGA-to-ESP32 deterministic status snapshot (`0x30`) carrying actual safety state, control flags, hard-limit status, watchdog timeout state, retained ML state, emergency state, and required-sensor validity.
- FPGA status transmitter with periodic/state-change delivery and pending-event coalescing.
- Locked-priority FPGA transmit arbiter so status and sensor frames share one UART without byte interleaving.
- Mixed FPGA message stream decoder with independent sensor/status sequence freshness gates.
- ESP32-S3 bounded pending-message queue so multiple valid frames in one UART receive chunk are not silently discarded.
- Cross-language status golden-frame tests plus VHDL status-transmitter and link-arbiter testbenches.
- Bidirectional ForgeSense Link v1 reference with FPGA-to-edge sensor snapshots and edge-to-FPGA ML observations.
- Signed normalized temperature, vibration RMS, current and explicit sensor validity wire contract.
- FPGA sample scheduler, local millisecond timebase, sensor-frame transmitter, UART RX/TX and board-level integration core.
- Persistent last-accepted FPGA intelligence state so accepted warning/critical results are not cleared by silence or rejected traffic.
- ESP32-S3 ESP-IDF application scaffold with configurable UART, sequence checks, link-loss handling and bounded ML transmission.
- Host-testable fixed-memory C++ edge inference runtime using an eight-sample feature window.
- Deterministic Python-to-C++ reference-model export and byte-for-byte reproducibility test.
- CRC32-protected fixed-size diagnostic event record and ESP32-S3 NVS ring storage.
- Sensor acquisition, event record and multi-scenario validation documentation.
- Seven-scenario deterministic validation matrix covering normal operation, developing faults, sensor invalidity, link loss and emergency input.
- Regression coverage for retained ML warning state and critical intelligence during first operational startup.
- Executable deterministic machine and sensor simulator.
- Synthetic normal, bearing degradation, overcurrent, cooling-loss, and sensor-dropout scenarios.
- Compact versioned anomaly-detection baseline and model artifact export.
- ForgeSense Link Protocol v1 with CRC-16/CCITT-FALSE, sequence freshness, and ML compatibility checks.
- Python reference codec and cross-language golden frames.
- Host-testable C++ protocol and stream parsers.
- Synthesizable VHDL hard-limit monitor, watchdog, safety state machine, protocol receiver, and integrated safety core.
- Self-checking VHDL safety and protocol testbenches.
- Virtual anomaly and closed-loop control demos.
- Implementation checks for Python, host C++, VHDL and repository policy.

### Fixed

- Expanded the canonical reference-model training envelope from a narrow settled subsection to the complete settled normal operating trace, preventing a false critical classification later in the modeled normal run.
- Retained the last accepted ML health state in both the software oracle and FPGA logic instead of treating it as a one-cycle frame pulse.
- Prevented a critical first accepted ML observation from transiently entering RUN or energizing the protected output.
- Prevented ML warm-up from expiring the communication watchdog before operational readiness.
- Prevented replayed, duplicate, incompatible, stale or corrupt observations from resetting the intelligence watchdog.
- Reset the ML feature window after required sensor invalidity or edge-link loss.
- Processed all bytes in each ESP32 UART receive chunk so a newer complete sensor frame is not discarded when multiple frames arrive together.
- Locked C++ ML payload length to the protocol's normative 14-byte payload through shared golden-frame tests.

## 2026-09-10

### Added

- Initial project foundation.
- Engineering documentation, safety model, security policy, contribution workflow, roadmap, and controlled development license.
