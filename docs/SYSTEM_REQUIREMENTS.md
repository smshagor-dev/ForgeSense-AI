# System Requirements

Status: initial baseline. Numeric limits marked TBD must be fixed before physical
output control is enabled.

## Reference use case

The first reference setup monitors and controls a current-limited low-voltage DC
motor or fan used as a laboratory test load.

## Functional requirements

| ID | Requirement |
| --- | --- |
| FR-001 | The system shall acquire temperature, vibration, and current-related signals. |
| FR-002 | The FPGA shall evaluate hard safety limits independently of ML inference. |
| FR-003 | The FPGA shall expose a deterministic state machine with startup, run, warning, shutdown, fault-latched, and controlled-recovery behavior. |
| FR-004 | The edge MCU shall compute versioned feature vectors and an anomaly/health result. |
| FR-005 | ML results shall include freshness information sufficient for the FPGA to reject stale results. |
| FR-006 | Loss of FPGA/MCU communication shall produce a documented degraded or safe state. |
| FR-007 | The system shall record fault cause, control state, and relevant measurements for later analysis. |
| FR-008 | A local dashboard shall present telemetry without owning safety-critical outputs. |
| FR-009 | Simulation shall support deterministic normal and fault scenarios without physical hardware. |
| FR-010 | Critical behavior shall be testable automatically. |

## Safety requirements

| ID | Requirement |
| --- | --- |
| SR-001 | ML output shall never override a hard FPGA shutdown condition. |
| SR-002 | Emergency input shall have a deterministic path to a safe output state. |
| SR-003 | Invalid, malformed, out-of-range, stale, or unsupported intelligence messages shall be rejected. |
| SR-004 | Watchdog expiry shall produce an explicitly defined control state. |
| SR-005 | Reset during an active fault shall not silently re-enable the controlled load. |
| SR-006 | Recovery from a latched critical fault shall require explicit documented conditions. |
| SR-007 | Unknown protocol versions shall fail closed for control-affecting commands. |

## Performance targets

Initial targets, subject to measurement:

- deterministic hard-fault reaction: bounded independently of ML latency;
- intelligence update rate: suitable for slowly evolving condition-monitoring faults;
- local operation: no internet connection required;
- model memory: within ESP32-S3 deployment budget;
- telemetry loss: must not stop deterministic safety evaluation;
- reproducible simulation: identical seed and configuration produce identical golden traces.

## Electrical constraints

- FPGA/MCU digital interfaces use compatible low-voltage logic levels.
- Experimental outputs remain current-limited and low voltage.
- Any higher-energy load interface requires isolation/protection designed for that use case.
- No mains switching is part of the initial reference system.

## Open decisions

- exact FPGA board/device;
- exact ESP32-S3 module;
- current-sensor topology;
- vibration-sensor topology;
- temperature-sensor topology;
- UART versus SPI reference transport;
- hard-limit values;
- control-loop and sampling frequencies;
- output-driver topology.

Open decisions must be closed with measured requirements, not convenience alone.
