# ForgeSense AI Roadmap

This roadmap separates **repository engineering implementation** from **external physical/product evidence**. Source completion must never be used to imply bench validation, manufacturing readiness, certification, or real-machine performance.

## Repository engineering implementation — complete

The ForgeSense v1 repository scope is complete and machine-tracked by `engineering/completion_manifest_v1.json`.

### Foundation and system contract

- [x] Repository identity, contribution, conduct, security and development license
- [x] Documentation map and IP/publication discipline
- [x] Frozen low-voltage 12 V motor/fan reference use case
- [x] Selected Tang Nano 9K + ESP32-S3 architecture
- [x] Temperature/vibration/current sensor channels and normalized units
- [x] Warning/critical hard-limit reference values
- [x] FPGA/MCU responsibility and authority matrix
- [x] Startup, run, warning, shutdown, fault-latched and controlled-recovery behavior
- [x] UART 115200 8N1 reference transport
- [x] Versioned frame format, CRC, sequence, freshness and timeout rules
- [x] Read-only telemetry schema and dashboard authority boundary

### Executable digital twin and qualification

- [x] Deterministic machine/current/temperature/vibration model
- [x] Deterministic scenario seeds and golden behavior
- [x] Sensor noise model
- [x] Sensor dropout model
- [x] Sensor bias and time-drift model
- [x] Sensor saturation model
- [x] Sensor stuck-value model
- [x] Fault injection for bearing, overcurrent, cooling loss, link loss, emergency and invalid sensors
- [x] Extended normal virtual soak qualification
- [x] Replay/communication abuse qualification
- [x] Reset/startup fail-safe qualification
- [x] Dataset-shift/stuck-current hard-limit qualification

### FPGA deterministic domain

- [x] Clock/reset and input synchronization
- [x] UART RX/TX and shared transmit arbitration
- [x] TMP117 I2C acquisition and identity checking
- [x] ADXL355 SPI acquisition/configuration readback
- [x] ADS131M02 mode-1 acquisition, register verification and frame CRC
- [x] Normalization, freshness supervision and vibration RMS
- [x] Hard-limit monitor
- [x] Watchdog and stale/invalid intelligence rejection
- [x] Deterministic safety state machine
- [x] Fault latch and controlled recovery
- [x] Output interlock and independent E-stop observation
- [x] Tang Nano 9K physical top, frozen application pin map and CST/SDC source
- [x] Self-checking RTL/testbench source set
- [x] Gowin build scripts and target definition

### ESP32-S3 edge domain

- [x] ESP-IDF production application scaffold
- [x] Fixed-memory stream parser/serializer
- [x] Sequence/integrity/freshness validation
- [x] 8-sample feature extraction
- [x] Deterministic compact inference interface
- [x] Link-loss/degraded behavior
- [x] Persistent CRC-protected event records
- [x] Read-only host telemetry
- [x] Local monitoring API/dashboard with no actuator routes
- [x] Separate transparent commissioning firmware
- [x] Separate calibration-maintenance firmware

### ML release engineering

- [x] Dataset schema/provenance contract
- [x] Reproducible synthetic reference dataset generator
- [x] Time/scenario-aware split policy
- [x] Classical diagonal-Gaussian anomaly baseline
- [x] Deterministic embedded model export
- [x] Model card
- [x] Virtual false-terminal/fault-detection evaluation report
- [x] Explicit decision not to promote a compact neural model without representative physical evidence
- [x] Version/model/schema compatibility checks
- [x] Target latency/memory listed as external measurement gates

### End-to-end virtual system

- [x] Simulator → sensing → inference → bounded FPGA decision loop
- [x] Corrupt/replayed/stale intelligence rejection
- [x] Communication-loss shutdown behavior
- [x] Sensor invalidity fail-closed behavior
- [x] Reset/startup and emergency scenarios
- [x] Deterministic validation matrix and executable qualification report

### Reference electronics source package

- [x] Component-backed `HW-BL-004` baseline
- [x] Protected 12 V input architecture
- [x] 5 V and quiet 3.3 V power tree
- [x] 15 mOhm + INA181A1 current front end
- [x] Independent TLV3201 analog trip reference
- [x] UCC27511A/CSD18540Q5B protected output reference
- [x] Normally-closed fail-high E-stop architecture
- [x] ADS131M02/ADXL355/TMP117 support contracts
- [x] BOM/package/net-endpoint/schematic contracts
- [x] PCB net-class/layout rules and bring-up procedure
- [x] Behavioral SPICE source models
- [x] Hardware analytical consistency checker

### Calibration, provisioning and recovery

- [x] Dedicated load-disabled read-only diagnostic stream
- [x] Diagnostic capture with integrity/authority checks
- [x] Independent-reference session assembly
- [x] Current/temperature/accelerometer characterization
- [x] Repeated-run review and uncertainty screening
- [x] Campaign orchestration and evidence-index hashing
- [x] Offline source-provenance/bundle verification
- [x] Reviewer-ready change package and external-signing payload
- [x] Explicit human approval gate
- [x] Current/temperature integer coefficient derivation and quantization regression
- [x] Add-only approved calibration source profile
- [x] Exact 48-byte `CalibrationRecord v1` generation
- [x] Strict non-wrapping sequence/anti-rollback policy
- [x] Dual-slot staged NVS storage and exact readback
- [x] Physically gated maintenance-only write path
- [x] External P-256 signed maintenance authorization
- [x] Monotonic recovery using a new higher sequence
- [x] Per-device SHA-256 audit ledger
- [x] Dual-signed maintenance-authority transition

### Security and release engineering

- [x] System threat model
- [x] Repository hazard analysis
- [x] Production/dashboard write-authority separation
- [x] Private-key isolation from repository/device tooling
- [x] ESP32-S3 Secure Boot v2 / flash-encryption release-policy contract
- [x] Secure-release sdkconfig policy checker
- [x] Firmware build-provenance SHA-256 manifest tool
- [x] No automated irreversible eFuse/security enablement from repository tooling
- [x] Machine-readable engineering completion manifest/checker

## External physical/product evidence — required before product readiness

These tasks are intentionally **not** marked complete from source code alone:

- [ ] Retain a successful supported-toolchain GHDL compile/run for the full selected-device/physical-top suites
- [ ] Retain successful Gowin synthesis, place-and-route, utilization and timing-closure reports
- [ ] Build the production and maintenance ESP-IDF targets on the selected ESP32-S3 toolchain and retain artifacts
- [ ] Measure ESP32-S3 latency, peak memory and current draw
- [ ] Verify physical J5 wiring, UART/SPI/I2C signal integrity and I2C rise time
- [ ] Verify actual sensor identities, accuracy, noise, mounting and bandwidth
- [ ] Execute three or more real calibration runs with independent reference uncertainty
- [ ] Verify shunt heating, current-sense drift, comparator threshold/chatter and eFuse waveforms
- [ ] Verify TVS/flyback transient energy, surge/EMC/noise immunity and thermal behavior
- [ ] Complete verified KiCad footprint binding, ERC/DRC and manufacturing outputs
- [ ] Fabricate/assemble and perform documented board bring-up
- [ ] Execute real soak, brownout and repeated power-cycle testing
- [ ] Measure real-machine false alarms, missed faults and detection lead time
- [ ] Enable/verify Secure Boot and flash encryption on controlled hardware with retained eFuse/readback evidence
- [ ] Perform any required product certification or machine-specific functional-safety assessment

## Future research directions

Potential research extensions include uncertainty-aware multi-sensor confidence, adaptive sampling, formal control-invariant proofs, physical installed-image attestation, hardware-backed monotonic counters, fleet learning, and selected feature/inference acceleration.

These are future research opportunities, not missing ForgeSense v1 repository implementation.
