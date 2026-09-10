# ForgeSense AI Documentation

This directory is the engineering source of truth for system behavior, interfaces, safety assumptions, implementation evidence, hardware decisions, verification, and publication discipline.

## Start here

- [`VISION.md`](VISION.md) — product/research direction and engineering boundaries.
- [`SYSTEM_REQUIREMENTS.md`](SYSTEM_REQUIREMENTS.md) — functional, safety, performance, and electrical requirements.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — responsibility split between sensors, FPGA, ESP32-S3, ML, dashboard, and output control.
- [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) — executable code and current evidence.
- [`TRANSPORT_AND_CONTROL.md`](TRANSPORT_AND_CONTROL.md) — byte-stream validation, freshness, watchdog, and closed-loop control path.
- [`SENSOR_ACQUISITION.md`](SENSOR_ACQUISITION.md) — normalized sensor units, validity, sampling, and FPGA-to-edge wire contract.
- [`SENSOR_CONTRACT.md`](SENSOR_CONTRACT.md) — generated cross-language sensor ranges, freshness limits, and FPGA supervision rules.
- [`SENSOR_FRONTEND.md`](SENSOR_FRONTEND.md) — deterministic calibration, RMS extraction, diagnostics, and normalized hardware boundary.
- [`SENSOR_PHY_REFERENCE.md`](SENSOR_PHY_REFERENCE.md) — vendor-neutral ADC/temperature/accelerometer transport, calibration record, self-test, and electronics boundary.
- [`FIRMWARE.md`](FIRMWARE.md) — ESP32-S3 runtime, UART service, inference, persistence, and host telemetry responsibilities.
- [`DEVICE_TELEMETRY.md`](DEVICE_TELEMETRY.md) — ESP32-S3-to-PC read-only telemetry records, freshness, and host bridge.
- [`TELEMETRY_API.md`](TELEMETRY_API.md) — local read-only monitoring API, authority model, freshness, and dashboard contract.
- [`EVENT_RECORDS.md`](EVENT_RECORDS.md) — fixed-size persistent event-record format and integrity checks.
- [`VALIDATION_MATRIX.md`](VALIDATION_MATRIX.md) — deterministic scenario acceptance matrix and current results.
- [`SAFETY_MODEL.md`](SAFETY_MODEL.md) — deterministic safety authority and failure behavior.
- [`VERIFICATION.md`](VERIFICATION.md) — verification expectations and evidence policy.
- [`HARDWARE_DESIGN.md`](HARDWARE_DESIGN.md) — electronics, protection, power, sensing, and PCB design rules.
- [`FPGA_VHDL.md`](FPGA_VHDL.md) — RTL structure and VHDL engineering rules.
- [`AI_ML.md`](AI_ML.md) — dataset, model, evaluation, and deployment requirements.
- [`IP_AND_PUBLICATION.md`](IP_AND_PUBLICATION.md) — prior-art, disclosure, and publication discipline.

The root [`ROADMAP.md`](../ROADMAP.md) tracks future engineering work. The root `README.md` is the project overview; this documentation set should remain precise and evidence-driven.
