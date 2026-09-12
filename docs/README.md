# ForgeSense AI Documentation

This directory is the engineering source of truth for system behavior, interfaces, safety assumptions, implementation evidence, hardware decisions, verification, and publication discipline.

## Start here

- [`VISION.md`](VISION.md) — product/research direction and engineering boundaries.
- [`SYSTEM_REQUIREMENTS.md`](SYSTEM_REQUIREMENTS.md) — frozen v1 functional, safety, timing, maintenance, and electrical requirements.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — responsibility split between sensors, FPGA, ESP32-S3, ML, dashboard, and output control.
- [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) — current source/executable implementation and external evidence boundary.
- [`ENGINEERING_COMPLETION.md`](ENGINEERING_COMPLETION.md) — formal 100% repository-engineering completion definition and physical-evidence separation.
- [`THREAT_MODEL.md`](THREAT_MODEL.md) — system trust boundaries, threats, controls, residual risks, and security invariants.
- [`HAZARD_ANALYSIS.md`](HAZARD_ANALYSIS.md) — repository-level electrical/control/calibration/ML hazard analysis.
- [`SOFTWARE_QUALIFICATION.md`](SOFTWARE_QUALIFICATION.md) — deterministic virtual soak, replay abuse, reset, sensor impairment, and shift qualification.
- [`TRANSPORT_AND_CONTROL.md`](TRANSPORT_AND_CONTROL.md) — byte-stream validation, freshness, watchdog, and closed-loop control path.
- [`SENSOR_ACQUISITION.md`](SENSOR_ACQUISITION.md) — normalized sensor units, validity, sampling, and FPGA-to-edge wire contract.
- [`SENSOR_CONTRACT.md`](SENSOR_CONTRACT.md) — generated cross-language sensor ranges, freshness limits, and FPGA supervision rules.
- [`SENSOR_FRONTEND.md`](SENSOR_FRONTEND.md) — deterministic calibration, RMS extraction, diagnostics, and normalized hardware boundary.
- [`SENSOR_PHY_REFERENCE.md`](SENSOR_PHY_REFERENCE.md) — acquisition, calibration record, self-test, and electronics boundary.
- [`SENSOR_DEVICE_DRIVERS.md`](SENSOR_DEVICE_DRIVERS.md) — TMP117, ADXL355, and ADS131M02 register-level FPGA acquisition and verification boundary.
- [`SENSOR_BEHAVIORAL_VERIFICATION.md`](SENSOR_BEHAVIORAL_VERIFICATION.md) — bus-level selected-sensor models, fault injection, combined acquisition verification, and evidence limits.
- [`TANG_NANO_9K_INTEGRATION.md`](TANG_NANO_9K_INTEGRATION.md) — frozen Tang Nano 9K J5 pin map, physical top, CST/SDC constraints, and Gowin build entry point.
- [`PHYSICAL_BRINGUP.md`](PHYSICAL_BRINGUP.md) — safe first-bitstream, wiring, test points, staged bench checks, and evidence-recording procedure.
- [`COMMISSIONING_UTILITY.md`](COMMISSIONING_UTILITY.md) — ESP32-S3 raw bridge, smoke heartbeat/echo measurement, read-only production observation, and bench-record auto-population.
- [`CALIBRATION_DIAGNOSTIC_STREAM.md`](CALIBRATION_DIAGNOSTIC_STREAM.md) — dedicated load-disabled FPGA image, diagnostic message `0x32`, transparent ESP32-S3 bridge path, PC evidence capture, and authority boundary.
- [`CALIBRATION_SESSION_ASSEMBLY.md`](CALIBRATION_SESSION_ASSEMBLY.md) — combine trusted diagnostics with independent reference measurements, SHA-256 evidence, uncertainty, and board provenance into a standard calibration capture.
- [`CALIBRATION_CAPTURE.md`](CALIBRATION_CAPTURE.md) — hashed bench evidence, current/temperature/accelerometer characterization, fit-quality metrics, and review-only calibration proposals.
- [`CALIBRATION_REVIEW.md`](CALIBRATION_REVIEW.md) — repeated-run consistency, declared measurement uncertainty, conservative engineering uncertainty screening, and source-controlled review boundary.
- [`CALIBRATION_CAMPAIGN.md`](CALIBRATION_CAMPAIGN.md) — orchestrate repeated sessions into an atomic campaign bundle with review output, artifact hashes, and a tamper-evident integrity index.
- [`CALIBRATION_BUNDLE_VERIFICATION.md`](CALIBRATION_BUNDLE_VERIFICATION.md) — verify campaign tamper evidence and original-source provenance, prepare reviewer-only change packages, and export an external-signing payload without accessing private keys.
- [`CALIBRATION_SOURCE_CHANGE.md`](CALIBRATION_SOURCE_CHANGE.md) — bind explicit reviewer approval to deterministic integer coefficient quantization, hard-safety non-regression, and an add-only source-controlled calibration profile patch.
- [`CALIBRATION_PROVISIONING.md`](CALIBRATION_PROVISIONING.md) — derive and verify exact `CalibrationRecord v1` images, enforce strict sequence ordering, and stage dual-slot NVS storage without exposing a remote provisioning command.
- [`CALIBRATION_MAINTENANCE_PROVISIONING.md`](CALIBRATION_MAINTENANCE_PROVISIONING.md) — use a separate default-disabled maintenance image with pinned P-256 public-key verification, external detached signing, dual physical gates, signed PREPARE/COMMIT, exact readback, retained evidence, and reboot recovery verification.
- [`CALIBRATION_RECOVERY.md`](CALIBRATION_RECOVERY.md) — restore an earlier approved coefficient set only through a new higher sequence while preserving exact active-record, signed-maintenance, and audit continuity.
- [`CALIBRATION_AUDIT_LEDGER.md`](CALIBRATION_AUDIT_LEDGER.md) — maintain a per-device append-structured SHA-256 calibration history, exact live record/signer continuity, and explicitly verified authority-transition events.
- [`MAINTENANCE_AUTHORITY_TRANSITION.md`](MAINTENANCE_AUTHORITY_TRANSITION.md) — rotate the maintenance trust anchor only through a reviewed rebuilt image, old/new signatures over the same payload, post-install read-only verification, and an unchanged-calibration audit transition.
- [`REFERENCE_CIRCUITS.md`](REFERENCE_CIRCUITS.md) — component-backed 12 V current sensing, analog hard trip, protected motor output, E-stop, and SPICE references.
- [`HARDWARE_BASELINE_V1.md`](HARDWARE_BASELINE_V1.md) — `HW-BL-004` protected power entry, selected reference parts, precision sensor support, physical pin mapping, schematic contracts, and evidence boundary.
- [`HARDWARE_DESIGN.md`](HARDWARE_DESIGN.md) — electronics, protection, power, sensing, and PCB design rules.
- [`FIRMWARE.md`](FIRMWARE.md) — ESP32-S3 runtime, UART service, inference, persistence, and host telemetry responsibilities.
- [`DEVICE_TELEMETRY.md`](DEVICE_TELEMETRY.md) — ESP32-S3-to-PC read-only telemetry records, freshness, and host bridge.
- [`TELEMETRY_API.md`](TELEMETRY_API.md) — local read-only monitoring API, authority model, freshness, and dashboard contract.
- [`EVENT_RECORDS.md`](EVENT_RECORDS.md) — fixed-size persistent event-record format and integrity checks.
- [`VALIDATION_MATRIX.md`](VALIDATION_MATRIX.md) — deterministic scenario acceptance matrix and current results.
- [`SAFETY_MODEL.md`](SAFETY_MODEL.md) — deterministic safety authority and failure behavior.
- [`VERIFICATION.md`](VERIFICATION.md) — verification expectations and evidence policy.
- [`FPGA_VHDL.md`](FPGA_VHDL.md) — RTL structure and VHDL engineering rules.
- [`AI_ML.md`](AI_ML.md) — dataset, model, evaluation, and deployment requirements.
- [`IP_AND_PUBLICATION.md`](IP_AND_PUBLICATION.md) — prior-art, disclosure, and publication discipline.

Hardware implementation artifacts live under `hardware/`. The active electrical sources include the protected power-entry, sensor-support, selected-device and interconnect profiles; preliminary BOM; machine-readable schematic contract; package/MPN manifest; net-endpoint freeze table; bring-up contracts; and the calibration diagnostic/session/capture/review/campaign/approval/source-change/provisioning/audit/authority-transition policies.

Primary verification gates include `make hardware-check`, `make firmware-host`, all calibration/maintenance checks, `make software-qualification-check`, `make ml-release-check`, `make release-security-check`, and `make engineering-complete-check`. The completion gate verifies the machine-readable repository scope while keeping external physical/tool evidence explicitly separate.

The root [`ROADMAP.md`](../ROADMAP.md) now distinguishes completed v1 repository engineering from physical/product validation. The root `README.md` is the project overview; this documentation set remains the detailed engineering source of truth.
