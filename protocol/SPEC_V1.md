# ForgeSense Link Protocol v1

## Purpose

This protocol carries bounded intelligence and status information between the deterministic FPGA domain and the ESP32-S3 domain. An accepted ML observation can influence only documented state transitions; it cannot override hard FPGA faults.

## Frame

All multi-byte integers are little-endian.

| Field | Size | Meaning |
| --- | ---: | --- |
| SOF | 2 | `A5 5A` |
| version | 1 | `01` for this specification |
| message_type | 1 | typed payload identifier |
| sequence | 2 | unsigned rolling sequence |
| payload_length | 2 | payload bytes |
| timestamp_ms | 4 | sender monotonic time modulo 2^32 |
| payload | variable | message-specific |
| CRC-16/CCITT-FALSE | 2 | over bytes from `version` through final payload byte |

CRC parameters: polynomial `0x1021`, initial value `0xFFFF`, no reflection, no final XOR.

Unknown versions or malformed frames are rejected.

## Message types

| Value | Name | Current control-path status |
| ---: | --- | --- |
| `0x10` | ML observation | implemented |
| `0x20` | heartbeat | reserved |
| `0x30` | status | reserved |

A reserved message type must not affect safety state until its acceptance and failure semantics are separately specified and verified.

## ML observation payload

| Field | Size | Notes |
| --- | ---: | --- |
| model_id | 2 | deployed model family |
| model_version | 2 | exact model revision |
| feature_schema_version | 2 | exact feature contract |
| flags | 2 | bit 0 = observation valid |
| anomaly_q15 | 2 | 0..32767 maps to 0..1 |
| health_class | 1 | 0 normal, 1 warning, 2 critical, 3 abstain |
| confidence_q8 | 1 | 0..255 maps to 0..1 |
| inference_age_ms | 2 | age of represented sample window |

The v1 ML payload is 14 bytes and the complete ML frame is therefore 28 bytes.

An FPGA-side gate must reject incompatible model/schema identifiers, observations without the valid flag, stale observations, duplicate/replayed sequence numbers, and CRC-invalid frames.

Sequence freshness uses modular unsigned 16-bit ordering. A candidate is newer when `(candidate - previous) mod 65536` is in `1..32767`.

## Stream behavior

A receiver may receive bytes in arbitrary chunks and may encounter unrelated or corrupted bytes before a valid frame. Implementations must resynchronize on the two-byte start marker and must not expose partially decoded values as a valid observation.

The current FPGA receiver performs early rejection for an unsupported protocol version, unsupported control-path message type, wrong ML payload length, or invalid health-class value, and performs final rejection on CRC mismatch.

## Watchdog behavior

The intelligence watchdog is not evidence that arbitrary bytes are arriving. Only a fully decoded observation that also passes the model/schema/age/sequence gate may kick the operational watchdog.

During feature-window/model warm-up, `startup_done` remains deasserted and operational intelligence supervision is held reset. After `startup_done` is asserted, missing, malformed, incompatible, stale, or replayed observations do not kick the watchdog and therefore lead to the defined communication-loss behavior.

## Safety behavior

A missing or rejected observation never clears a hard warning, hard critical condition, emergency request, or latched fault. ML critical output can request the documented controlled shutdown state, while emergency and hard-critical inputs retain deterministic priority and fault-latching authority.
