# Implementation Status

This document tracks code that exists and is executable. It is intentionally separate from the longer-term roadmap.

## Executable now

### Virtual plant and sensors

`simulator/forgesense_sim` provides deterministic low-voltage machine traces for normal operation, bearing degradation, overcurrent, cooling loss, and explicit sensor dropout.

### Edge ML runtime

`ml/forgesense_ml` contains the compact diagonal-Gaussian baseline plus a deterministic feature-window runtime. Invalid sensor samples reset the current window so stale pre-dropout measurements cannot silently flow into a new observation.

### Closed-loop safety oracle

`simulator/forgesense_sim/closed_loop.py` mirrors the FPGA safety authority at a cycle-policy level. It combines hard limits, intelligence freshness, watchdog supervision, warning/shutdown transitions, fault latching, and controlled recovery. This gives integration tests an executable reference before physical hardware exists.

### FPGA/MCU protocol

`protocol/SPEC_V1.md` defines framing, CRC-16/CCITT-FALSE, sequence freshness, model/schema compatibility, and bounded ML observation fields. Python supports both complete-frame decoding and incremental stream resynchronization.

### Firmware boundary

`firmware/components/forgesense_protocol` contains a host-testable C++20 frame parser, fixed-memory byte-stream decoder, and freshness gate. CRC-invalid, incompatible, stale, and replayed observations are not accepted as watchdog health evidence.

### Deterministic FPGA safety logic

`fpga/rtl` now includes the hard-limit monitor, watchdog, safety state machine, CRC implementation, raw-byte ML frame receiver, freshness gate, and integrated `forgesense_core`. The receiver validates the same normative 28-byte frame used by Python and C++.

The intelligence watchdog is held reset until `startup_done` so feature-window/model warm-up does not cause a false communication shutdown. After operational readiness, only accepted fresh observations kick it.

## Verification baseline

Automated checks now cover:

- deterministic simulator replay and injected sensor/fault scenarios;
- ML baseline separation and feature-window invalidation;
- CRC corruption and arbitrary stream chunking;
- stream resynchronization after garbage/corruption;
- stale and duplicate/replayed intelligence rejection;
- sequence wrap behavior;
- watchdog hold during pre-operational warm-up;
- replay traffic failing to keep the watchdog alive;
- host C++ frame and stream checks with warnings treated as errors;
- VHDL safety-state assertions;
- VHDL decoding of the shared protocol golden frame;
- a deterministic closed-loop bearing-degradation run.

The current closed-loop reference injects progressive bearing degradation at sample 220 and reaches bounded ML shutdown at sample 238 while the hard critical threshold remains false. This validates the integration path, not physical predictive-maintenance performance.

## Deliberately not claimed yet

The current plant model is not a physical motor model, the anomaly detector is not a production predictive-maintenance model, and the hard-limit defaults are not safe hardware limits. Physical fault lead time, reliability, false-alarm rates, electrical safety, timing closure, and industrial suitability require measured hardware evidence.
