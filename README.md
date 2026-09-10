# ForgeSense AI

**Low-cost FPGA + TinyML predictive maintenance, fail-safe control, and industrial automation research platform.**

ForgeSense AI is a hardware-software co-design project for building an intelligent industrial controller that combines deterministic FPGA safety logic with edge machine learning. The system is being designed to observe machine condition, detect abnormal behavior, estimate developing faults, and trigger bounded automation while preserving a hard real-time safety path that does not depend on ML inference.

> **Project status:** Foundation and pre-hardware implementation. The repository is intentionally structured so RTL, firmware, ML, simulation, electronics, PCB, dashboard, and validation work can evolve together from a single set of system requirements.

## Why ForgeSense AI

Industrial predictive-maintenance products commonly separate condition monitoring from machine control. ForgeSense AI explores a tighter architecture in which:

- FPGA logic owns deterministic timing, interlocks, watchdogs, emergency behavior, and final safety authority.
- Edge ML analyzes multivariate sensor behavior and produces bounded health, anomaly, and fault information.
- The intelligent layer can recommend or request actions, but it cannot override hard safety rules.
- The same interfaces are designed for simulation first and physical hardware later.
- Cost, reproducibility, inspectability, and offline operation are treated as first-class design constraints.

The project does **not** currently claim to be the first implementation of these ideas. Any novelty, patentability, or prior-art claim must be established through a documented technical and legal review before public claims are made.

## Intended V1 System

The initial complete system targets a small motor, fan, pump, conveyor, or comparable electromechanical load.

```text
Machine / Test Load
        |
        v
+-----------------------------+
| Sensors                     |
| temperature | vibration     |
| current     | digital I/O   |
+-------------+---------------+
              |
              v
+-----------------------------+
| FPGA Safety & Control       |
| acquisition | filtering     |
| FSM         | interlocks    |
| watchdog    | fault limits  |
+-------------+---------------+
              | bounded protocol
              v
+-----------------------------+
| ESP32-S3 Edge Intelligence  |
| features | TinyML inference |
| health   | anomaly scoring  |
| telemetry | local API       |
+-------------+---------------+
              |
        +-----+------+
        |            |
        v            v
  Dashboard       Event Log

FPGA --------------------------------> Safe output driver / relay / shutdown
```

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

The repository will grow into the following structure:

```text
ForgeSense-AI/
├── fpga/                 # VHDL RTL, constraints, reusable IP, testbenches
├── firmware/             # ESP32-S3 firmware and hardware abstraction
├── ml/                   # datasets, preprocessing, training, evaluation, export
├── simulator/            # machine, sensor, fault, and protocol simulation
├── hardware/             # schematics, PCB, BOM, manufacturing outputs
├── dashboard/            # local monitoring and configuration UI
├── protocol/             # FPGA <-> edge processor protocol specification
├── tests/                # cross-component and integration tests
├── tools/                # developer utilities and reproducibility scripts
├── docs/                 # system, architecture, safety, verification documentation
└── .github/              # contribution templates and repository automation
```

Directories containing implementation code will be added with their own README and build instructions when development begins.

## Planned Technical Stack

| Area | Initial direction |
| --- | --- |
| FPGA RTL | VHDL, synthesizable RTL, self-checking testbenches |
| FPGA target | Low-cost Tang Nano-class device for early validation |
| Edge MCU | ESP32-S3 |
| ML | Python training pipeline, compact quantized edge inference |
| Sensors | Temperature, vibration/IMU, current, discrete safety inputs |
| FPGA/MCU link | Versioned UART or SPI protocol with integrity and freshness checks |
| Outputs | Protected low-voltage driver path and relay/MOSFET abstraction |
| Dashboard | Local-first web interface and telemetry API |
| PCB | Two-layer prototype where signal integrity and safety constraints allow |
| CI | Deterministic checks for docs, RTL, firmware, ML, and tests as each subsystem lands |

Specific parts are not frozen until electrical requirements and sourcing are validated.

## Safety Boundary

ForgeSense AI is a research and engineering platform, not a certified industrial safety controller. Until appropriate hardware protections, hazard analysis, verification, and applicable certification are completed:

- do not use it to protect people from hazardous machinery;
- do not switch mains voltage directly from experimental circuitry;
- do not rely on ML output as a safety function;
- do not bypass a machine's existing certified protection system;
- use current-limited, isolated, low-voltage test loads during development.

See [`docs/SAFETY_MODEL.md`](docs/SAFETY_MODEL.md) and [`SECURITY.md`](SECURITY.md) as the repository develops.

## Documentation

Start with [`docs/README.md`](docs/README.md). The documentation set is designed to cover:

- product vision and engineering scope;
- system requirements and assumptions;
- architecture and interface contracts;
- circuit and PCB design rules;
- VHDL/FPGA design conventions;
- ML data, training, evaluation, and deployment rules;
- firmware responsibilities;
- safety and threat models;
- verification and validation strategy;
- roadmap and release criteria;
- intellectual-property and publication discipline.

## Roadmap

The detailed roadmap is maintained in [`ROADMAP.md`](ROADMAP.md). Near-term work is ordered around reducing technical uncertainty before buying or fabricating hardware:

1. Freeze system boundaries, safety invariants, signals, and interfaces.
2. Build the executable digital twin and sensor/fault simulator.
3. Implement synthesizable VHDL safety/control logic with self-checking tests.
4. Implement the edge firmware protocol and ML runtime boundary.
5. Establish a reproducible ML training/evaluation baseline using synthetic and later real data.
6. Integrate end-to-end virtual fault scenarios and recovery behavior.
7. Validate on low-cost FPGA + ESP32-S3 hardware.
8. Design and manufacture the custom electronics only after the reference implementation is stable.

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
