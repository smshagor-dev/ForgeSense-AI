# ForgeSense AI

**Low-cost FPGA + TinyML predictive maintenance, fail-safe control, and industrial automation research platform.**

ForgeSense AI is a hardware-software co-design project for building an intelligent industrial controller that combines deterministic FPGA safety logic with edge machine learning. The system is being designed to observe machine condition, detect abnormal behavior, estimate developing faults, and trigger bounded automation while preserving a hard real-time safety path that does not depend on ML inference.

> **Project status:** Active pre-hardware implementation. The repository now includes an executable virtual plant, edge ML baseline/runtime, a versioned FPGA/MCU protocol, host-tested firmware parsing, a raw-byte FPGA receiver, deterministic safety logic, and a closed-loop software safety oracle.

## Why ForgeSense AI

Industrial predictive-maintenance products commonly separate condition monitoring from machine control. ForgeSense AI explores a tighter architecture in which:

- FPGA logic owns deterministic timing, interlocks, watchdogs, emergency behavior, and final safety authority.
- Edge ML analyzes multivariate sensor behavior and produces bounded health, anomaly, and fault information.
- The intelligent layer can recommend or request actions, but it cannot override hard safety rules.
- The same interfaces are designed for simulation first and physical hardware later.
- Cost, reproducibility, inspectability, and offline operation are treated as first-class design constraints.

The project does **not** currently claim to be the first implementation of these ideas. Any novelty, patentability, or prior-art claim must be established through a documented technical and legal review before public claims are made.

## Current Executable System

```text
Synthetic/real sensors
        |
        v
Feature window + edge ML
        |
        v
ForgeSense Link v1
        |
        v
Byte-stream receiver + CRC
        |
        v
Compatibility / freshness gate
        |
        v
Deterministic FPGA safety core -----------------> Protected output path
        |                                              |
        +--> state / fault / warning telemetry         v
                                                  Test machine/load
```

The current reference includes deterministic normal and fault scenarios, a compact anomaly detector, protocol CRC and replay protection, watchdog supervision, hard-limit monitoring, fault latching, controlled recovery, and a closed-loop integration demo.

## Core Engineering Principles

### Safety authority is deterministic

ML output is treated as untrusted advisory input. Hard limits, emergency inputs, watchdog behavior, state transitions, and output interlocks remain in synthesizable deterministic logic.

### Simulation before hardware

Every major interface should have a software or RTL simulation path before a physical board is required. Hardware procurement should validate an existing design rather than define it.

### Failure-aware communication

Loss, delay, corruption, replay, reset, stale inference, or malformed messages between the FPGA and edge processor must result in a defined safe behavior.

### Measurable ML

Models must be evaluated against explicit datasets, splits, metrics, thresholds, latency, memory use, and false-alarm behavior. A model is not accepted because a demo appears to work.

### Low-cost by design

The reference target is a low-cost FPGA board plus ESP32-S3 for early hardware validation, followed by a custom PCB only after interfaces and safety behavior stabilize.

### Reproducible engineering

Requirements, assumptions, test vectors, datasets, model artifacts, RTL simulations, firmware builds, PCB revisions, and validation results should be traceable to source control.

## Repository Layout

```text
ForgeSense-AI/
├── fpga/                 # VHDL RTL, protocol receiver, safety core, testbenches
├── firmware/             # ESP32-S3-oriented C++ protocol/runtime components
├── ml/                   # preprocessing, model baseline, edge feature runtime
├── simulator/            # machine, sensor, fault, and closed-loop reference behavior
├── hardware/             # schematics, PCB, BOM, manufacturing outputs
├── dashboard/            # local monitoring and configuration UI
├── protocol/             # FPGA <-> edge processor protocol specification/reference
├── tests/                # cross-component and integration tests
├── tools/                # executable demos and reproducibility utilities
├── docs/                 # architecture, safety, verification and implementation docs
└── .github/              # contribution templates and repository automation
```

Directories containing implementation code include their own build or usage notes as they mature.

## Technical Stack

| Area | Current direction |
| --- | --- |
| FPGA RTL | VHDL-2008, synthesizable deterministic control and protocol logic |
| FPGA target | Low-cost Tang Nano-class device for early validation |
| Edge MCU | ESP32-S3 |
| ML | Python training/reference runtime, compact edge-oriented inference |
| Sensors | Temperature, vibration/IMU, current, discrete safety inputs |
| FPGA/MCU link | ForgeSense Link v1 with CRC, versioning, freshness and compatibility checks |
| Outputs | Protected low-voltage driver path and relay/MOSFET abstraction |
| Dashboard | Local-first web interface and telemetry API |
| PCB | Two-layer prototype where electrical constraints allow |
| CI | Python, host C++, VHDL and repository policy checks |

Specific physical parts are not frozen until electrical requirements and sourcing are validated.

## Run the Current Reference

Python tests:

```bash
make test
```

Virtual anomaly demo:

```bash
make demo
```

Closed-loop control demo:

```bash
make closed-loop
```

Host firmware protocol/stream tests:

```bash
make firmware-host
```

The current deterministic closed-loop reference injects progressive bearing degradation at sample 220 and reaches a bounded ML-requested shutdown at sample 238 while the hard critical threshold remains false. This is integration evidence only, not physical-machine performance evidence.

## Safety Boundary

ForgeSense AI is a research and engineering platform, not a certified industrial safety controller. Until appropriate hardware protections, hazard analysis, verification, and applicable certification are completed:

- do not use it to protect people from hazardous machinery;
- do not switch mains voltage directly from experimental circuitry;
- do not rely on ML output as a safety function;
- do not bypass a machine's existing certified protection system;
- use current-limited, isolated, low-voltage test loads during development.

See [`docs/SAFETY_MODEL.md`](docs/SAFETY_MODEL.md), [`docs/TRANSPORT_AND_CONTROL.md`](docs/TRANSPORT_AND_CONTROL.md), and [`SECURITY.md`](SECURITY.md).

## Documentation

Start with [`docs/README.md`](docs/README.md) and [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md). The documentation set covers product vision, system requirements, architecture, electronics, FPGA/VHDL rules, ML contracts, firmware responsibilities, safety, verification, protocol behavior, roadmap, and IP/publication discipline.

## Roadmap

The detailed roadmap is maintained in [`ROADMAP.md`](ROADMAP.md). Near-term work is ordered around reducing technical uncertainty before buying or fabricating hardware: close interface contracts, deepen the virtual twin and fault model, harden synthesizable RTL, complete the ESP32-S3 transport/runtime boundary, expand ML evaluation, then validate on low-cost hardware before committing to a custom PCB.

## Contributing

This repository is currently under controlled development. Read [`CONTRIBUTING.md`](CONTRIBUTING.md), [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md), and [`SECURITY.md`](SECURITY.md) before proposing changes.

Do not disclose suspected vulnerabilities in public issues.

## Intellectual Property and Licensing

The project is currently maintained under an **all-rights-reserved development license** while architecture, prior art, publication strategy, and potential protectable work are evaluated. No permission to copy, redistribute, manufacture from, commercialize, sublicense, or create derivative works is granted unless explicitly stated in writing.

See [`LICENSE`](LICENSE) and [`docs/IP_AND_PUBLICATION.md`](docs/IP_AND_PUBLICATION.md).

A future public-source license can be selected deliberately once the project's publication and IP strategy is settled.

## Author

**Md Shahanur Islam Shagor**  
Full-Stack Web Developer & AI / Autonomous Systems Engineer  
GitHub: [@smshagor-dev](https://github.com/smshagor-dev)

---

ForgeSense AI is being built as an engineering system first: every intelligent behavior should be bounded, every safety behavior should be testable, and every hardware decision should be justified by measurable requirements.
