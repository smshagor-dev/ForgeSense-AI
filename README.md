# ForgeSense AI

**Low-cost FPGA + TinyML predictive maintenance, fail-safe control, and industrial automation research platform.**

ForgeSense AI is a hardware-software co-design project for building an intelligent industrial controller that combines deterministic FPGA safety logic with edge machine learning. The system is being designed to observe machine condition, detect abnormal behavior, estimate developing faults, and trigger bounded automation while preserving a hard real-time safety path that does not depend on ML inference.

> **Project status:** Foundation and executable pre-hardware reference implementation are now in place. The repository includes a deterministic machine/sensor simulator, an ML anomaly baseline, a versioned FPGA↔ESP32 protocol, host-testable firmware parsing, and synthesizable VHDL safety/control logic.

## Why ForgeSense AI

Industrial predictive-maintenance products commonly separate condition monitoring from machine control. ForgeSense AI explores a tighter architecture in which:

- FPGA logic owns deterministic timing, interlocks, watchdogs, emergency behavior, and final safety authority.
- Edge ML analyzes multivariate sensor behavior and produces bounded health, anomaly, and fault information.
- The intelligent layer can recommend or request actions, but it cannot override hard safety rules.
- The same interfaces are designed for simulation first and physical hardware later.
- Cost, reproducibility, inspectability, and offline operation are treated as first-class design constraints.

The project does **not** currently claim to be the first implementation of these ideas. Any novelty, patentability, or prior-art claim must be established through a documented technical and legal review before public claims are made.

## Current Executable Stack

```text
Deterministic virtual machine
        ↓
Synthetic temperature / vibration / current sensors
        ↓
Versioned feature vector
        ↓
Compact anomaly model
        ↓
ForgeSense Link Protocol v1
        ↓
Freshness / compatibility gate
        ↓
FPGA safety state logic
        ↓
Safe output decision
```

The end-to-end virtual demo is runnable now and is covered by automated tests. See [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md).

## Intended System

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

```text
ForgeSense-AI/
├── fpga/                 # VHDL RTL and testbenches
├── firmware/             # ESP32-S3-side protocol/runtime code
├── ml/                   # training, evaluation, model export
├── simulator/            # deterministic plant and sensor simulation
├── hardware/             # schematics, PCB, BOM, manufacturing outputs
├── dashboard/            # local monitoring/configuration UI
├── protocol/             # FPGA ↔ edge processor contract
├── tests/                # automated cross-component tests
├── tools/                # reproducibility and virtual-demo tools
├── docs/                 # system and engineering documentation
└── .github/              # workflows and contribution templates
```

## Quick Start

Python tests:

```bash
PYTHONPATH=simulator:ml:protocol/python python -m pytest
```

End-to-end virtual demo:

```bash
PYTHONPATH=simulator:ml:protocol/python python tools/run_virtual_demo.py
```

Firmware protocol host test:

```bash
g++ -std=c++20 -Wall -Wextra -Werror \
  -Ifirmware/components/forgesense_protocol/include \
  firmware/components/forgesense_protocol/forgesense_protocol.cpp \
  firmware/tests/protocol_test.cpp \
  -o build/firmware_protocol_test
./build/firmware_protocol_test
```

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
| CI | Python, host C++, protocol-vector, and VHDL verification |

Specific physical parts are not frozen until electrical requirements and sourcing are validated.

## Safety Boundary

ForgeSense AI is a research and engineering platform, not a certified industrial safety controller. Until appropriate hardware protections, hazard analysis, verification, and applicable certification are completed:

- do not use it to protect people from hazardous machinery;
- do not switch mains voltage directly from experimental circuitry;
- do not rely on ML output as a safety function;
- do not bypass a machine's existing certified protection system;
- use current-limited, isolated, low-voltage test loads during development.

See [`docs/SAFETY_MODEL.md`](docs/SAFETY_MODEL.md) and [`SECURITY.md`](SECURITY.md).

## Documentation

Start with [`docs/README.md`](docs/README.md) and [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md). The documentation covers system requirements, architecture, hardware design rules, FPGA/VHDL conventions, ML contracts, firmware boundaries, safety, verification, roadmap, and IP/publication discipline.

## Roadmap

The detailed roadmap is maintained in [`ROADMAP.md`](ROADMAP.md). Near-term engineering work is ordered around reducing technical uncertainty before buying or fabricating hardware:

1. Extend the executable digital twin and fault-injection matrix.
2. Complete the byte-stream parser and FPGA protocol receive path.
3. Add ESP32-S3 transport and feature-window scheduling.
4. Add stronger ML baselines and reproducible evaluation reports.
5. Integrate end-to-end virtual fault/recovery scenarios.
6. Validate on low-cost FPGA + ESP32-S3 hardware.
7. Design and manufacture the custom electronics after the reference implementation is stable.

## Contributing

This repository is currently under controlled development. Read [`CONTRIBUTING.md`](CONTRIBUTING.md), [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md), and [`SECURITY.md`](SECURITY.md) before proposing changes.

Do not disclose suspected vulnerabilities in public issues.

## Intellectual Property and Licensing

The project is currently maintained under an **all-rights-reserved development license** while architecture, prior art, publication strategy, and potential protectable work are evaluated. No permission to copy, redistribute, manufacture from, commercialize, sublicense, or create derivative works is granted unless explicitly stated in writing.

See [`LICENSE`](LICENSE) and [`docs/IP_AND_PUBLICATION.md`](docs/IP_AND_PUBLICATION.md).

## Author

**Md Shahanur Islam Shagor**  
Full-Stack Web Developer & AI / Autonomous Systems Engineer  
GitHub: [@smshagor-dev](https://github.com/smshagor-dev)

---

ForgeSense AI is being built as an engineering system first: every intelligent behavior should be bounded, every safety behavior should be testable, and every hardware decision should be justified by measurable requirements.
