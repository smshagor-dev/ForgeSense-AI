# Hazard Analysis

## Scope and scale

This is a repository-level engineering hazard analysis for the low-voltage ForgeSense reference platform. It documents hazard controls and verification expectations; it is not a functional-safety certification, SIL/PL assessment, or machine-specific risk assessment.

Severity is ranked `S1` minor, `S2` equipment damage, `S3` serious equipment/fire risk in the laboratory context. Likelihood is intentionally not assigned without physical evidence.

| ID | Hazard | Severity | Detection/control layers | Repository acceptance condition | Physical evidence still required |
| --- | --- | ---: | --- | --- | --- |
| H-01 | Excess motor/load current | S3 | 15 mOhm sensing, FPGA hard current limit, ~3.47 A analog comparator trip, ~4.04 A eFuse limit, 5 A fuse | protection ordering and arithmetic remain machine-checked | trip tolerance, eFuse waveform, fuse coordination, shunt heating |
| H-02 | Overtemperature | S2 | TMP117 identity/transport checks, normalized temperature hard limit, ML warning only secondary | invalid/stale temperature fails closed; ML cannot override limit | placement, thermal lag, machine-specific threshold validation |
| H-03 | Excess vibration/mechanical fault | S2 | ADXL355 identity/config verification, freshness/plausibility, RMS feature, hard/ML thresholds | invalid sensor fails closed; deterministic RMS implementation covered | mounting, bandwidth, real fault signatures |
| H-04 | Emergency stop demanded or wiring open | S3 | normally-closed loop, fail-high `ESTOP_INHIBIT_5V`, direct gate-driver inhibit, separate FPGA observation | physical inhibit remains independent of software/ML | continuity, debounce/noise, cable fault tests |
| H-05 | FPGA/ESP32 communication loss | S2 | supervised watchdog; no ML frame can keep authority without freshness | timeout produces deterministic shutdown | physical UART interruption timing |
| H-06 | Corrupt/replayed intelligence | S2 | CRC, version/type/length, model/schema, sequence and age gates | corrupt/replay does not reset watchdog or clear retained warning | physical fault-injection on UART |
| H-07 | Sensor bus fault or stale sample | S2 | per-device identity/config checks, CRC where supported, freshness supervisor | required invalid sensor drives deterministic fault path | measured bus faults/noise |
| H-08 | MOSFET stuck on / driver fault | S3 | independent E-stop inhibit, upstream eFuse/fuse, flyback network | software is not the sole turn-off layer | hardware fault injection and energy analysis |
| H-09 | Supply overvoltage/transient | S3 | SMBJ15A TVS, TPS259470L OVLO, protected branch | voltage ratings/order are source-checked | surge waveform/clamp energy/EMC tests |
| H-10 | Supply undervoltage/brownout | S2 | TPS259470L UVLO, fail-safe startup/reset logic | reset/startup cannot silently enable load | brownout ramp and repeated power-cycle tests |
| H-11 | Incorrect calibration | S2 | independent references, repeated-run review, explicit approval, quantization regression, signed write, exact readback | calibration cannot change hard-safety source files; monotonic record sequence | real reference instruments and uncertainty |
| H-12 | Calibration storage corruption | S2 | CRC32 record, dual NVS slots, inactive-slot write/readback, highest-valid recovery | corrupt/ambiguous slots rejected | power-loss injection on target |
| H-13 | Unauthorized maintenance write | S2 | dedicated image, physical gates, P-256 signature, device/sequence/root binding | unsigned/old-sequence write rejected | physical gate wiring and key operations |
| H-14 | Maintenance authority compromise/rotation error | S2 | dual-signed transition, clean Git/source/image binding, post-install fingerprint, audit event | arbitrary fingerprint drift rejected | key custody and actual firmware install validation |
| H-15 | Dashboard/telemetry failure | S1 | read-only monitor; no control authority | loss cannot stop FPGA safety evaluation | operational monitoring procedure |
| H-16 | ML false negative | S2 | deterministic hard limits remain independent | ML absence/wrong output cannot override hard fault | real-data missed-fault study |
| H-17 | ML false positive | S1/S2 | ML can request bounded warning/shutdown but not bypass safety; recovery controlled | virtual normal scenario has no terminal action | real false alarms per operating hour |
| H-18 | Firmware tamper | S2 | secure-release policy, Secure Boot v2/flash-encryption requirements, provenance hashes | release profile is machine-checkable and private-key free | device eFuse/readback evidence |

## Core safety invariants

1. `load_enable` is never a direct ML or dashboard output.
2. Emergency or hard critical conditions dominate every intelligence result.
3. Invalid required sensor state is a hard fault, not a request to continue on ML estimates.
4. Reset/startup begins without load authority and requires documented readiness.
5. Communication freshness is required continuously after operational readiness.
6. Recovery is explicit and cannot bypass an active hard/emergency condition.
7. Calibration affects measurement normalization only through reviewed records; it does not authorize hard-limit changes.
8. Security failure must degrade toward shutdown/fault rather than expand actuator authority.

## Review triggers

This analysis must be revised when a hard limit changes, the load voltage/current envelope changes, a protection component changes, calibration-record semantics change, a new actuator route is introduced, or physical evidence contradicts the current assumptions.
