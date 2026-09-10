# Transport and Control Integration

This document describes the executable byte-stream-to-safety path used before physical hardware is connected.

## Data path

```text
ESP32-S3 inference result
        |
        v
ForgeSense Link v1 frame
        |
        v
UART byte stream
        |
        v
FPGA link_receiver
  - SOF resynchronization
  - version/type/length checks
  - CRC-16/CCITT-FALSE
        |
        v
intelligence_gate
  - valid flag
  - model identity
  - model version
  - feature schema
  - inference age
  - sequence freshness
        |
        v
safety_core
  - watchdog
  - hard limits
  - deterministic state machine
  - output interlock
```

Only an observation accepted by the intelligence gate may kick the operational intelligence watchdog or influence an ML-related state transition.

## Warm-up rule

Feature-window construction and model warm-up happen before `startup_done` is asserted. The operational intelligence watchdog is held reset during this interval. Once `startup_done` is asserted, missing, invalid, stale, incompatible, or replayed observations do not kick the watchdog and therefore eventually force the defined shutdown state.

This prevents two opposite failure modes:

- shutting down before the first valid inference can exist;
- allowing malformed traffic to masquerade as a healthy intelligence link.

## Stream recovery

The Python and C++ stream decoders accept arbitrarily chunked input and search for the two-byte start marker after garbage or corruption. The FPGA receiver performs the same start-marker resynchronization and rejects unsupported version, message type, payload length, health class, or CRC.

The current FPGA receiver implements the fixed 28-byte ML-observation frame from protocol v1. Other message types remain reserved until their safety semantics are specified and tested.

## Cross-language golden frame

The normative test vector remains:

```text
a55a011007000e00393000000100010001000100ff6701e01900e3c8
```

It represents sequence 7, timestamp 12345 ms, model/schema identifiers 1, warning health class, anomaly Q15 `0x67FF`, confidence `0xE0`, inference age 25 ms, and CRC `0xC8E3` on the wire in little-endian order.

Python, C++ and VHDL tests use this same byte sequence.

## Current closed-loop evidence

The deterministic reference run trains the compact baseline on settled normal-operation data and then applies a progressive bearing-degradation scenario. With the current synthetic reference configuration:

- degradation begins at sample 220;
- the bounded ML path requests shutdown at sample 238;
- the hard critical threshold is still false at that shutdown point.

These numbers validate integration behavior only. They are not claims about physical fault lead time or industrial predictive-maintenance performance.
