# Persistent Event Records

## Purpose

ForgeSense AI retains sparse diagnostic evidence across ESP32-S3 resets without making storage part of the hard safety path.

Events answer when the edge runtime booted, when a required sensor became invalid, when the local FPGA sensor stream was lost or recovered, when ML changed to warning/critical, and what normalized measurements accompanied that transition.

## Binary record

Each record is 36 bytes with CRC-32/IEEE integrity protection.

| Field | Size |
| --- | ---: |
| magic (`FSEV`) | 4 |
| record version | 1 |
| severity | 1 |
| source | 1 |
| event code | 1 |
| event sequence | 4 |
| local monotonic_ms | 4 |
| FPGA state code / unknown marker | 1 |
| event flags | 1 |
| sensor validity flags | 2 |
| temperature_deci_c | 2 |
| vibration_milli_g | 2 |
| current_milli_a | 2 |
| anomaly_q15 | 2 |
| detail | 4 |
| CRC-32/IEEE | 4 |

CRC uses reflected polynomial representation `0xEDB88320`, initial `0xFFFFFFFF`, final XOR `0xFFFFFFFF`.

## Event categories

Initial codes cover boot, sensor invalid, link lost, link recovered, ML warning, ML critical, hard critical, emergency, and recovery. Some FPGA-originated categories remain reserved until the status/event return channel is implemented.

## NVS ring

The ESP32-S3 application stores encoded records in an NVS ring. The default ring contains 64 slots. Each record gets a monotonically increasing 32-bit journal sequence; slot selection is `sequence mod ring_size`.

When the ring wraps, the oldest slot is overwritten. Only sparse events are written; per-sample telemetry is intentionally excluded to reduce flash writes.

## Integrity and limits

CRC detects accidental corruption; it is not authentication. Persistent records are diagnostic evidence and are never trusted to command the FPGA. Any future tamper-evident logging requires an explicit cryptographic format and key-management design.
