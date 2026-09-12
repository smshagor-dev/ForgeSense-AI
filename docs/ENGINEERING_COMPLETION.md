# Repository Engineering Completion

## Status

**ForgeSense v1 repository engineering implementation: complete.**

This means the declared repository scope has source-controlled implementations for architecture/contracts, deterministic simulation, FPGA RTL, ESP32-S3 firmware references, selected sensor drivers, ML baseline/export/evaluation, telemetry/dashboard, calibration evidence and provisioning, signed maintenance, monotonic recovery, audit continuity, maintenance-authority transition, security/release policy, hazard analysis, and executable repository qualification.

It does **not** mean the physical product is complete. Repository completion is explicitly separate from external EDA execution, device provisioning, physical measurement, PCB fabrication, EMC/thermal testing, real-machine performance, and certification.

## 100% repository engineering implementation

The machine-readable source of truth is:

```text
engineering/completion_manifest_v1.json
```

Every item under `repository_scope` must be `complete` and every referenced evidence path must exist. `tools/check_engineering_completion.py` enforces this boundary and rejects missing implementation evidence.

Run:

```bash
make engineering-complete-check
```

The gate combines:

- deterministic sensor impairment regression;
- extended virtual software qualification;
- deterministic ML dataset/evaluation release artifacts;
- ESP32-S3 production-release security policy checks;
- repository completion-manifest verification;
- all existing calibration, maintenance, audit, hardware-contract, protocol, firmware-host, and RTL verification wiring through their existing targets/workflows.

## Scope completed in source

### System and deterministic control

- frozen v1 reference use case and responsibility boundaries;
- versioned FPGA/ESP32 protocol with CRC, sequence, freshness and timeout behavior;
- startup/run/warning/shutdown/fault/recovery state model;
- independent hard limits, watchdog and physical E-stop authority;
- selected sensor acquisition/normalization and freshness supervision;
- deterministic virtual plant and fault scenarios;
- sensor noise, bias, drift, saturation, stuck-value and dropout models.

### Edge intelligence and observability

- compact deterministic ML baseline;
- generated embedded model constants;
- 8-sample feature runtime;
- dataset provenance contract and reproducible synthetic dataset generator;
- model card and virtual evaluation report;
- local telemetry and read-only dashboard;
- persistent event records.

A more complex neural model is intentionally **not** promoted from synthetic-only evidence. The repository treats “not justified yet” as a closed engineering decision rather than adding complexity solely to satisfy a checklist.

### Calibration and maintenance trust

The source chain is implemented through:

```text
read-only diagnostics
→ independently referenced calibration sessions
→ repeated-run campaign/review
→ verified reviewer package
→ explicit approval
→ integer coefficient derivation
→ approved source profile
→ exact CalibrationRecord v1
→ external P-256 authorization
→ physical maintenance gates
→ signed PREPARE/COMMIT
→ dual-slot NVS readback
→ reboot verification
→ monotonic recovery
→ per-device SHA-256 audit chain
→ dual-signed maintenance-authority transition
```

None of these workflows can relax the FPGA hard-safety source baseline.

### Security and release engineering

- system threat model;
- hazard analysis;
- signed calibration-maintenance authorization;
- maintenance-authority rotation with old/new proof;
- ESP32-S3 production-release Secure Boot v2 / flash-encryption policy;
- firmware build-provenance hashing;
- private-key isolation;
- no automated irreversible eFuse actions from repository tooling.

## External evidence gates

The following are intentionally **not** converted into fake repository completion claims. They remain external evidence gates:

- retained successful Gowin synthesis/place-and-route/resource/timing reports;
- retained supported-toolchain GHDL execution where hosted infrastructure has not run;
- ESP-IDF target build plus measured target memory/latency;
- actual Secure Boot/flash-encryption/eFuse readback;
- verified KiCad footprints, ERC/DRC, Gerbers and manufacturing review;
- physical board continuity/bring-up/signal-integrity evidence;
- real calibration campaigns with independent instrument uncertainty;
- thermal, EMC, surge, long-duration soak, brownout and power-cycle evidence;
- real-machine fault signatures, false alarms, missed faults and lead time;
- certification or machine-specific functional-safety assessment.

Those gates determine physical/product readiness, not whether the repository engineering implementation is complete.

## Completion rule

No future change may keep the repository marked complete if it removes a declared evidence path, reintroduces a missing repository deliverable, weakens the hard-safety boundary, exposes maintenance writes through production/dashboard paths, or blurs physical evidence into source-only claims. The completion checker is therefore a regression gate, not a marketing percentage.
