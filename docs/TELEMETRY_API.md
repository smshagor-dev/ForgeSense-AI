# Local Telemetry and Monitoring API

## Purpose

ForgeSense exposes a local read-only monitoring surface so development tools and the dashboard can observe sensors, edge inference, and the FPGA's deterministic safety state without creating a second control authority.

The API is intentionally monitoring-only. It does not expose load enable, recovery, emergency reset, threshold mutation, or raw FPGA command routes.

## Authority model

`fpga_status` is the only source used for the displayed system state. An ML observation may report `CRITICAL`, but the API does not translate that into a machine state. If authoritative FPGA status is missing or stale, `system.state` becomes `UNKNOWN` rather than guessing from sensors or ML.

This is a deliberate safety and observability boundary.

## Local endpoints

The reference server binds to `127.0.0.1` by default.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/v1/health` | monitoring service health and status freshness |
| GET | `/api/v1/snapshot` | current combined sensor, FPGA status, and ML snapshot |
| GET | `/api/v1/events?limit=50` | bounded recent diagnostic transitions |
| GET | `/api/v1/stream?after=<revision>` | long-poll until telemetry revision changes |

`POST`, `PUT`, `PATCH`, and `DELETE` return `405 Method Not Allowed` from the reference server.

## Snapshot contract

The root schema identifier is `forgesense.telemetry.v1`. The main sections are:

- `system`: authoritative display state, authority identifier, monitoring-only marker and status freshness;
- `sensor`: normalized engineering units, validity, source sequence/timestamp and receive age;
- `fpga_status`: deterministic state, load/warning/fault flags and safety conditions reported by the FPGA;
- `ml`: model identity, anomaly score, health class, confidence and inference age.

Every source retains its own sequence and timestamp. Receive age is calculated by the monitoring process and is not used as a substitute for FPGA safety logic.

## Staleness

The monitoring store has a configurable status staleness threshold. Staleness affects only what the monitoring surface is willing to claim. It does not change FPGA behavior.

If FPGA status exceeds the monitoring freshness interval:

```text
system.state = UNKNOWN
system.status_fresh = false
```

Sensor and ML fields remain visible with their own `stale` markers for diagnostics.

## Diagnostic timeline

The in-memory monitor timeline records sparse transitions such as FPGA state changes, hard critical assertion, emergency assertion, communication timeout, hard warning, required-sensor invalidity/restoration, and ML health-class changes.

This timeline complements the ESP32 NVS event ring. It is not a durable audit log and must not be treated as authenticated evidence.

## Browser surface

`dashboard/` is a dependency-free local UI served by the same process. It shows the authoritative FPGA state separately from the edge anomaly score, normalized sensor values, deterministic safety flags, and recent diagnostic transitions.

Static assets use same-origin requests. The reference server sends a restrictive Content Security Policy and `X-Content-Type-Options: nosniff`.

## Run

```bash
make dashboard
```

The default demonstration feeds the monitoring stack from the deterministic bearing-degradation simulation. It never sends actuator commands back into the controller.
