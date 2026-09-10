# ForgeSense Link Protocol v1

## Purpose

This protocol carries bounded intelligence and status information between the
deterministic FPGA domain and the ESP32-S3 domain. An accepted ML observation can
influence only documented state transitions; it cannot override hard FPGA faults.

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

CRC parameters: polynomial `0x1021`, initial value `0xFFFF`, no reflection,
no final XOR.

Unknown versions or malformed frames are rejected.

## Message types

| Value | Name |
| ---: | --- |
| `0x10` | ML observation |
| `0x20` | heartbeat |
| `0x30` | status |

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

An FPGA-side gate must reject incompatible model/schema identifiers, observations
without the valid flag, stale observations, duplicate/replayed sequence numbers,
and CRC-invalid frames.

Sequence freshness uses modular unsigned 16-bit ordering. A candidate is newer
when `(candidate - previous) mod 65536` is in `1..32767`.

## Safety behavior

A missing or rejected observation never clears a hard warning, hard critical
condition, emergency request, or latched fault. Communication loss is handled by
the FPGA watchdog policy independent of this message format.
