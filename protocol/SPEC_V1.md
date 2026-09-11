# ForgeSense Link Protocol v1

## Purpose

ForgeSense Link carries normalized sensor snapshots from the FPGA domain to the ESP32-S3 domain and bounded intelligence observations back to the deterministic FPGA safety domain. The protocol is small, versioned, checksummed, and independent of Wi-Fi or dashboard availability.

An accepted ML observation may influence only documented state transitions. It cannot override an emergency input, invalid-sensor policy, hard threshold, fault latch, or deterministic output interlock.

## Transport profile

The initial physical profile is UART 8-N-1 at 115200 baud. The binary frame format is transport-independent. All multi-byte integers are little-endian.

## Frame

| Field | Size | Meaning |
| --- | ---: | --- |
| SOF | 2 | `A5 5A` |
| version | 1 | `01` |
| message_type | 1 | typed payload identifier |
| sequence | 2 | unsigned rolling sequence |
| payload_length | 2 | payload bytes |
| timestamp_ms | 4 | sender-local monotonic milliseconds modulo 2^32 |
| payload | variable | message-specific |
| CRC-16/CCITT-FALSE | 2 | bytes from `version` through final payload byte |

CRC parameters: polynomial `0x1021`, initial value `0xFFFF`, no reflection, no final XOR. Malformed, CRC-invalid, unsupported-version, unsupported-length, and type-incompatible frames are rejected before use.

## Message types

| Value | Name | Initial direction |
| ---: | --- | --- |
| `0x10` | ML observation | ESP32-S3 -> FPGA |
| `0x11` | sensor snapshot | FPGA -> ESP32-S3 |
| `0x20` | heartbeat | reserved |
| `0x30` | status snapshot | FPGA -> ESP32-S3 |
| `0x31` | event | reserved |

The initial sensor and ML streams maintain independent 16-bit sequence counters.

## ML observation payload

Payload length: 14 bytes.

| Field | Size | Notes |
| --- | ---: | --- |
| model_id | 2 | deployed model family |
| model_version | 2 | exact model revision |
| feature_schema_version | 2 | exact feature contract |
| flags | 2 | bit 0 = observation valid |
| anomaly_q15 | 2 | 0..32767 maps to 0..1 |
| health_class | 1 | 0 normal, 1 warning, 2 critical, 3 abstain |
| confidence_q8 | 1 | 0..255 maps to 0..1 |
| inference_age_ms | 2 | edge-local processing age |

The FPGA rejects incompatible model/schema identifiers, observations without the valid flag, out-of-range fields, stale observations, duplicate/replayed sequence numbers, and CRC-invalid frames.

Accepted health state is retained in the FPGA domain until a newer accepted observation replaces it. A missing or rejected frame therefore cannot silently clear a previously accepted warning or critical result.

## Sensor snapshot payload

Payload length: 8 bytes.

| Field | Size | Type / unit |
| --- | ---: | --- |
| temperature_deci_c | 2 | signed int16, 0.1 °C |
| vibration_milli_g | 2 | uint16, 0.001 g RMS |
| current_milli_a | 2 | uint16, mA |
| sensor_flags | 2 | validity/quality bits |

Validity bits are bit 0 temperature, bit 1 vibration, bit 2 current; bits 3..15 are reserved and transmit zero.

The ESP32-S3 does not infer from a snapshot unless all features required by the deployed schema are valid. The first runtime clears its feature window whenever a required sensor becomes invalid. A separate sequence gate rejects duplicate or backwards sensor snapshots so repeated telemetry cannot artificially fill the inference window.

## Status snapshot payload

Payload length: 4 bytes. Status frames are emitted periodically and when the FPGA-visible safety or selected-device diagnostic state changes.

| Field | Size | Meaning |
| --- | ---: | --- |
| state_code | 1 | 0 startup, 1 run, 2 warning, 3 shutdown, 4 fault-latched, 5 recovery |
| control_flags | 1 | bit 0 load enabled, bit 1 warning active, bit 2 fault latched, bit 3 operational ready |
| safety_flags | 2 | bit 0 hard warning, bit 1 hard critical, bit 2 communication timeout, bit 3 retained ML warning, bit 4 retained ML critical, bit 5 emergency, bit 6 required sensors valid, bit 7 selected-device identity/configuration OK, bit 8 selected-device transport error |

Bits 9..15 are reserved and transmit zero. Bits 7 and 8 are diagnostic observations only; they do not grant the ESP32-S3 or monitoring software actuator authority and do not relax hard safety policy. The selected-device identity bit becomes true only when TMP117, ADXL355, and ADS131M02 startup identity/configuration checks have all succeeded. The transport-error bit reports a selected-device or normalized PHY transport/conditioning error observed by the FPGA path.

Status is diagnostic evidence from the deterministic FPGA domain; receiving it never grants the ESP32-S3 actuator authority. Sensor and status message types use separate rolling sequence spaces.

Golden status frame for sequence 0, timestamp `0x01020304`, warning state, load/warning/ready control flags, and hard-warning/ML-warning/sensors-valid safety flags:

```text
a55a01300000040004030201020b4900d118
```

The golden frame intentionally leaves selected-device diagnostic bits clear so the original status-vector compatibility example remains unchanged.

## Sequence freshness

A candidate sequence is newer when `(candidate - previous) mod 65536` is in `1..32767`. This permits wrap from 65535 to 0 while rejecting duplicates and backwards/replayed values.

## Timestamp model

`timestamp_ms` is local to the sender. FPGA and ESP32-S3 monotonic clocks are not assumed synchronized. A receiver must not subtract timestamps from different clock domains unless explicit synchronization is added. The ESP32-S3 computes `inference_age_ms` from its own receipt/inference timing.

## Startup and watchdog semantics

The FPGA begins with load authority disabled. Sensor frames may flow immediately. The ESP32-S3 fills its feature window and returns ML observations. Intelligence becomes operational only after a valid, compatible, fresh ML frame has been accepted.

Before that event the intelligence watchdog is held reset. Afterwards only accepted fresh ML observations kick it. CRC-invalid, stale, incompatible, and replayed traffic cannot keep the watchdog healthy.

A critical first accepted ML observation must not transiently energize the load; startup resolves directly to safe shutdown.

## Golden frames

ML observation:

```text
a55a011007000e00393000000100010001000100ff6701e01900e3c8
```

Sensor snapshot:

```text
a55a011134120800040302011f018e00b4050700d9b7
```

Python and host C++ verify both contracts. VHDL verifies the sensor transmitter against its matching sequence-zero golden frame.

## Safety behavior

Protocol acceptance is not actuator authority. The FPGA safety state machine remains the final decision layer. Communication loss, hard faults, invalid sensors, and emergency input have deterministic behavior independent of dashboard/network state.
