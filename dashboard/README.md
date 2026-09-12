# ForgeSense Industrial HMI

The dashboard is a local, read-only industrial monitoring interface for ForgeSense AI. It is served by `tools/run_dashboard.py` and consumes only the documented `/api/v1/*` monitoring endpoints.

Run from the repository root:

```bash
make dashboard
```

The default address is:

```text
http://127.0.0.1:8765
```

## HMI layout

The interface provides:

- a fixed industrial navigation rail;
- top-level system, FPGA safety, ML, communication, temperature, and current status cards;
- a machine overview schematic with live sensor tags and protected-output state;
- live temperature/current/vibration trend history built only from received telemetry;
- normalized sensor gauges;
- deterministic FPGA safety state and watchdog indicators;
- telemetry freshness, validity, and sequence information;
- recent diagnostic events;
- calibration/maintenance and security boundary summaries.

Calibration, provisioning, secure-boot state, firmware provenance, and authority-key details are **not fabricated from unavailable telemetry**. Panels explicitly state when those values are source-controlled, maintenance-only, offline evidence, or not exposed through the local monitor API.

## Authority boundary

The HMI intentionally exposes no actuator, provisioning, recovery, calibration-write, hard-limit-edit, or maintenance-authority mutation controls. It remains a visualization surface only; FPGA deterministic safety authority is unchanged.

The dashboard uses no external CDN or web dependency and remains usable on an isolated lab PC.
