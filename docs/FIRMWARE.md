# ESP32-S3 Firmware

## Role

The ESP32-S3 hosts edge intelligence, protocol handling, local telemetry, bounded
configuration, and event logging. It is intentionally outside the hard safety
trust boundary.

## Planned modules

```text
firmware/
├── main/
├── components/
│   ├── transport/
│   ├── protocol/
│   ├── features/
│   ├── inference/
│   ├── telemetry/
│   ├── config/
│   └── event_log/
├── test/
└── README.md
```

## Firmware invariants

- Parse before use; validate every externally supplied field.
- Reject unsupported protocol versions.
- Track frame sequence/freshness.
- Keep model version and feature schema bound together.
- Never represent a network/dashboard request as a raw unrestricted FPGA command.
- A firmware reset must be observable by the FPGA through timeout/startup behavior.
- Persistent configuration requires range validation and schema versioning.
- Logs must distinguish measurement, inference, requested action, accepted action, and fault response.

## Connectivity

Networking is optional for core operation. Loss of Wi-Fi must not disable local
measurement, inference, FPGA communication, or deterministic safety behavior.

## Update direction

A later deployment profile may support verified firmware updates. Production-style
updates should consider signed artifacts, rollback behavior, version compatibility,
and recovery from interrupted updates.
