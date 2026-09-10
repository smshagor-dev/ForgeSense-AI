# ForgeSense AI Documentation

This directory is the engineering source of truth for system behavior, interfaces, safety assumptions, implementation evidence, hardware design decisions, verification, and publication discipline.

## Start here

- [`VISION.md`](VISION.md) — product/research direction and engineering boundaries.
- [`SYSTEM_REQUIREMENTS.md`](SYSTEM_REQUIREMENTS.md) — functional, safety, performance, and electrical requirements.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — responsibility split between sensors, FPGA, ESP32-S3, ML, dashboard, and output control.
- [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) — what is executable now and what evidence exists.
- [`TRANSPORT_AND_CONTROL.md`](TRANSPORT_AND_CONTROL.md) — byte-stream, protocol validation, freshness, watchdog, and closed-loop safety path.
- [`SAFETY_MODEL.md`](SAFETY_MODEL.md) — deterministic safety authority and failure behavior.
- [`VERIFICATION.md`](VERIFICATION.md) — verification expectations and evidence policy.
- [`HARDWARE_DESIGN.md`](HARDWARE_DESIGN.md) — electronics, protection, power, sensing, and PCB design rules.
- [`FPGA_VHDL.md`](FPGA_VHDL.md) — RTL structure and VHDL engineering rules.
- [`FIRMWARE.md`](FIRMWARE.md) — ESP32-S3 firmware responsibilities.
- [`AI_ML.md`](AI_ML.md) — dataset, model, evaluation, and deployment requirements.
- [`IP_AND_PUBLICATION.md`](IP_AND_PUBLICATION.md) — prior-art, disclosure, and publication discipline.

The root [`ROADMAP.md`](../ROADMAP.md) tracks future engineering work. The root `README.md` is the public-facing project overview, while this documentation set should remain more precise and conservative than marketing material.
