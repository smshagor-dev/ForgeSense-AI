# System Requirements

Status: **ForgeSense v1 repository contract frozen.** Physical measurements remain separate evidence gates.

## Reference use case

ForgeSense v1 monitors and controls a current-limited **12 V low-voltage DC motor/fan laboratory load**. It is an engineering/research reference, not a certified machine-safety controller and not a mains-switching design.

Selected compute/sensing baseline:

- FPGA: Sipeed Tang Nano 9K (`GW1NR-LV9QN88PC6/I5`), 27 MHz onboard clock;
- edge MCU: ESP32-S3-DevKitC-1;
- transport: UART 115200 8N1;
- temperature: TMP117;
- vibration: ADXL355;
- current acquisition: 15 mOhm Kelvin shunt + INA181A1 gain 20 + ADS131M02;
- protected load path: UCC27511A + CSD18540Q5B with independent normally-closed E-stop inhibit;
- input protection: 5 A fuse + SMBJ15A + TPS259470L eFuse.

## Functional requirements

| ID | Requirement | Repository implementation |
| --- | --- | --- |
| FR-001 | Acquire temperature, vibration and current-related signals. | Selected-device FPGA controllers and normalized sensor frontend. |
| FR-002 | Evaluate hard safety limits independently of ML. | FPGA `hard_limit_monitor` and safety FSM. |
| FR-003 | Expose startup, run, warning, shutdown, fault-latched and controlled-recovery behavior. | FPGA RTL and software oracle. |
| FR-004 | Compute versioned feature vectors and edge anomaly/health results. | ESP32 portable inference runtime with 8-sample feature window. |
| FR-005 | Carry freshness information so stale intelligence is rejected. | timestamp/sequence/inference-age gates and watchdog. |
| FR-006 | Communication loss produces deterministic shutdown behavior. | supervised intelligence watchdog. |
| FR-007 | Record fault/control/measurement context. | CRC-protected event records and read-only telemetry. |
| FR-008 | Present telemetry without owning actuator authority. | local read-only API/dashboard. |
| FR-009 | Support deterministic normal/fault scenarios without hardware. | simulator, scenario matrix and software qualification. |
| FR-010 | Critical behavior is automatically testable. | Python/C++/VHDL tests and source-contract checkers. |
| FR-011 | Calibration changes require independent evidence/review and may not silently affect hard safety. | calibration campaign, approval, source-change and provisioning gates. |
| FR-012 | Physical calibration writes require dedicated maintenance authority. | physical gates + externally signed PREPARE/COMMIT + dual-slot storage. |
| FR-013 | Recovery never decrements calibration sequence. | recovery workflow restores coefficients using a new higher sequence. |
| FR-014 | Maintenance-authority rotation must be explicit and auditable. | dual-signed old/new authority transition bound to reviewed source/image. |

## Safety requirements

| ID | Requirement |
| --- | --- |
| SR-001 | ML output shall never override a hard FPGA shutdown condition. |
| SR-002 | Emergency input shall have a deterministic path to safe output and an independent physical gate-driver inhibit. |
| SR-003 | Invalid, malformed, out-of-range, stale, replayed or unsupported intelligence shall be rejected. |
| SR-004 | Watchdog expiry shall remove load authority through documented shutdown behavior. |
| SR-005 | Reset/startup shall not silently re-enable the controlled load. |
| SR-006 | Recovery from shutdown/fault shall require explicit conditions and shall not bypass an active hard/emergency condition. |
| SR-007 | Unknown protocol versions/types/schema combinations shall fail closed for control-affecting traffic. |
| SR-008 | Invalid required sensor state shall be treated as hard critical. |
| SR-009 | Production/dashboard/telemetry surfaces shall not expose calibration provisioning or hard-limit mutation. |
| SR-010 | Calibration/maintenance tooling shall not relax analog, E-stop or FPGA hard-safety limits. |
| SR-011 | Security failures shall degrade toward denial/shutdown, not expanded actuator authority. |

## Frozen hard-limit reference values

The repository reference uses:

| Channel | Warning | Critical |
| --- | ---: | ---: |
| Temperature | 65.0 C | 80.0 C |
| Vibration RMS | 600 mg | 1000 mg |
| Current | 2500 mA | 3200 mA |

These are v1 engineering reference values shared by the FPGA RTL and software oracle. They are **not** certified machine-specific safe limits.

Independent current protection remains layered:

```text
~3.47 A analog comparator hard trip
< ~4.04 A TPS259470L eFuse reference current limit
< 5 A passive fuse
```

## Timing and transport requirements

- FPGA reference clock: 27 MHz.
- UART: 115200 baud, 8N1.
- normalized sensor snapshot rate: 10 Hz.
- FPGA safety-status reference rate: 2 Hz plus state-change delivery.
- intelligence watchdog reference: 1500 ms in the selected physical composition.
- TMP117 I2C requested maximum: 400 kHz.
- ADXL355 SPI requested maximum: 2 MHz, mode 0.
- ADS131M02 SPI requested maximum: 2 MHz, CPOL=0/CPHA=1 behavior.
- bus clock dividers shall round frequency down rather than exceed a configured device maximum.

## Sensor validity and units

Wire units are frozen by `hardware/profiles/sensor_contract_v1.json`:

- temperature: signed deci-degrees C;
- vibration: non-negative milli-g RMS;
- current: non-negative milliampere;
- every required channel carries validity/freshness semantics;
- invalid required sensor state fails closed in deterministic safety logic.

## Security and maintenance requirements

- production ESP32 release policy requires Secure Boot v2 and flash-encryption release-mode settings before a production security claim;
- repository tooling must not store/load production private keys or automatically burn irreversible eFuses;
- calibration maintenance requires a dedicated firmware target, physical maintenance enable, independent load-inhibit sense, exact target identity, signed authorization and monotonic sequence checks;
- maintenance authority rotation requires old-authority continuity plus new-authority proof of possession over the same transition payload;
- audit history is tamper-evident SHA-256 chaining, not immutable storage or a digital signature;
- raw flash/NVS snapshot rollback and installed-image attestation require separate hardware/device evidence.

## Performance and evidence requirements

Repository-executable targets cover deterministic virtual behavior, host C++ runtime behavior, source contracts and VHDL test sources. The following values must be **measured on physical hardware** before product-performance claims:

- ESP32-S3 inference latency, peak memory and current draw;
- FPGA synthesis/place-and-route resources and timing closure;
- real UART/SPI/I2C signal integrity;
- sensor accuracy/noise/drift and real calibration uncertainty;
- false alarms per operating hour, missed-fault rate and detection lead time;
- thermal, surge, EMC, soak, brownout and power-cycle behavior.

## Completion boundary

There are no unresolved repository-architecture decisions for ForgeSense v1. Future changes to the selected devices, hard limits, transport, record formats or authority model are controlled revisions, not open baseline questions.

Repository implementation completion is tracked in `engineering/completion_manifest_v1.json` and verified by `make engineering-complete-check`. Physical/product readiness remains governed by the external evidence gates listed in `docs/ENGINEERING_COMPLETION.md`.
