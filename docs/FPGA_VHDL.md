# FPGA and VHDL Engineering Rules

## Design objective

The FPGA implementation is the deterministic control and safety authority of the
reference system. Readability and verification matter more than clever RTL.

## Planned structure

```text
fpga/
├── rtl/
│   ├── reset/
│   ├── io/
│   ├── sensing/
│   ├── safety/
│   ├── protocol/
│   └── top/
├── tb/
├── constraints/
├── scripts/
└── README.md
```

## RTL rules

- Use synthesizable VHDL for production RTL.
- Use `numeric_std` for arithmetic.
- Prefer explicit widths and signedness.
- Avoid inferred latches.
- Synchronize asynchronous inputs before synchronous state logic.
- Treat clock-domain crossings as explicit interfaces.
- Reset behavior must be documented for safety-relevant state.
- Enumerated states are preferred for major control state machines.
- Counters and timeout values must derive from named clock-frequency assumptions.
- Intelligence messages must pass validity and freshness checks before influencing state.

## Safety core

The safety core should remain small enough to reason about independently. It owns:

- hard-limit flags;
- emergency status;
- communication timeout;
- state machine;
- output enable/interlock;
- critical fault latch;
- controlled reset/recovery rule.

## Verification expectations

Self-checking testbenches should cover:

- reset from every relevant state;
- exact boundary values around thresholds;
- timeout at N-1, N, and N+1 cycles;
- malformed or unsupported frames;
- stale and duplicate intelligence;
- simultaneous hard fault and ML recommendation;
- communication disappearance and return;
- fault latch and recovery;
- output never energizing in forbidden states.

Waveforms are useful for diagnosis but assertions and machine-readable pass/fail
results are required for CI.

## Synthesis evidence

For the selected FPGA, track:

- logic utilization;
- register utilization;
- memory/DSP usage where applicable;
- achieved clock frequency;
- timing violations;
- warnings affecting correctness;
- reproducible tool version.
