# Product and Research Vision

## Problem

Low-cost industrial monitoring often ends at dashboards and alerts, while machine
control remains a separate subsystem. Intelligent models can identify patterns
that threshold logic misses, but allowing probabilistic inference to directly own
a safety output creates an unacceptable failure mode.

ForgeSense AI investigates a co-designed controller where deterministic FPGA logic
and edge ML cooperate without sharing the same authority.

## Product direction

The system should be able to:

- acquire multiple machine-condition signals;
- detect hard unsafe conditions deterministically;
- estimate anomalies and developing faults locally;
- expose machine health and evidence through a local interface;
- request bounded automation based on intelligent inference;
- continue safe operation when ML, networking, or telemetry is unavailable;
- run on low-cost hardware suitable for education, research, and small industrial experiments.

## Differentiation hypothesis

The interesting engineering contribution is not simply adding an ML model to an
FPGA board. The target architecture treats intelligence as a fallible subsystem
and makes its authority explicit, testable, time-bounded, and revocable.

Candidate differentiators to investigate include:

- hardware-enforced authority boundaries for ML decisions;
- stale-inference rejection in the deterministic control path;
- combined sensor/fault digital twin shared by RTL, firmware, and ML tests;
- uncertainty-aware degraded modes rather than binary AI control;
- reproducible low-cost hardware/software co-validation;
- traceable evidence from sensor sample to inference to control outcome.

These are research hypotheses until prior-art review and experiments support a
stronger claim.

## Non-goals for the first system

- replacing certified emergency-stop systems;
- direct control of hazardous high-energy machinery;
- cloud-dependent operation;
- unrestricted self-modifying control logic;
- opaque autonomous safety decisions;
- claiming predictive accuracy without representative data;
- claiming commercial certification before the required processes are completed.

## Success definition

ForgeSense AI succeeds when a low-cost reference system can demonstrate that:

1. deterministic safety behavior remains correct under ML failure;
2. ML adds measurable condition-monitoring value beyond fixed thresholds;
3. complete fault scenarios are repeatable in simulation and hardware;
4. interfaces and test evidence are reproducible by another engineer;
5. cost remains low enough for practical prototyping.
