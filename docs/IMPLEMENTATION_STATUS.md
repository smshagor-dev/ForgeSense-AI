# Implementation Status

This document tracks code that exists and is executable. It is intentionally
separate from the longer-term roadmap.

## Executable now

### Virtual plant and sensors

`simulator/forgesense_sim` provides deterministic low-voltage machine traces for
normal operation, bearing degradation, overcurrent, cooling loss, and explicit
sensor dropout.

### ML baseline

`ml/forgesense_ml` contains a compact diagonal-Gaussian anomaly detector with a
versioned export artifact. It establishes measurable model behavior and a TinyML
integration contract before more complex models are introduced.

### FPGA/MCU protocol

`protocol/SPEC_V1.md` defines framing, CRC-16/CCITT-FALSE, sequence freshness,
model/schema compatibility, and bounded ML observation fields. The Python codec
is the executable reference.

### Deterministic FPGA safety logic

`fpga/rtl` contains synthesizable VHDL for hard limits, watchdog behavior,
freshness gating, safety-state transitions, fault latching, controlled recovery,
and load-output interlocking.

### Firmware boundary

`firmware/components/forgesense_protocol` implements the protocol parser in
host-testable C++20 so byte-level behavior can be validated before ESP32-S3
transport code is introduced.

## Verification baseline

Automated checks cover deterministic simulator replay, injected bearing
degradation, explicit sensor invalidity, ML artifact round-trip, severe-fault
anomaly separation, CRC corruption rejection, stale and duplicate intelligence
rejection, sequence wrap behavior, host C++ protocol checks, and VHDL safety-state
assertions.

## Deliberately not claimed yet

The current plant model is not a physical motor model, the anomaly detector is
not a production predictive-maintenance model, and the hard-limit defaults are
not safe hardware limits. Those claims require measured hardware evidence.
