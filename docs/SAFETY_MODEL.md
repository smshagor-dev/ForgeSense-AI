# Safety Model

ForgeSense AI is not a certified safety controller. This document defines the
engineering safety model used during development and validation.

## Fundamental rule

**Probabilistic intelligence may reduce uncertainty, but it may not defeat a
hard deterministic safety condition.**

## Initial safety invariants

- A hard over-limit condition has priority over all intelligent recommendations.
- Emergency input cannot be masked by the MCU, dashboard, model, or network.
- A stale ML result cannot remain valid indefinitely.
- Communication loss cannot leave a previously granted risky action permanently active.
- Reset cannot silently clear a critical latched fault and energize the load.
- Unknown control-relevant messages are rejected.
- Out-of-range numeric values are rejected before state logic consumes them.
- Output enable requires all mandatory deterministic preconditions to be true.

## Trust model

Trusted for safety only after verification:

- minimal FPGA safety RTL;
- clock/reset assumptions explicitly validated;
- electrical output-disable path;
- hard sensor limits used by the safety core.

Not trusted as sole safety authority:

- ML model;
- ESP32-S3 application logic;
- Wi-Fi or network services;
- dashboard;
- remote clients;
- historical database;
- user-supplied configuration;
- non-safety analytics.

## Development operating envelope

Until a later hardware safety review:

- use low-voltage DC loads only;
- use a current-limited supply;
- keep an independent physical power disconnect available;
- do not connect to hazardous machinery;
- do not bypass certified machine protection;
- do not directly switch mains voltage.

## Hazard analysis format

Every identified hazard should record:

```text
Hazard ID
Initiating condition
Affected subsystem
Potential consequence
Existing prevention
Detection mechanism
Safe response
Residual risk
Verification test
Evidence reference
```

## ML-specific hazards

Validation must include:

- false positive during healthy operation;
- false negative during developing fault;
- confidence miscalibration;
- distribution shift;
- sensor drift;
- delayed inference;
- repeated old inference;
- corrupted model artifact;
- model/feature version mismatch.

The safe system response should not depend on the assumption that these failures
never occur.
