# ForgeSense AI

**Low-cost FPGA + edge ML predictive maintenance, fail-safe control, and industrial automation research platform.**

ForgeSense AI is a hardware-software co-design system that combines deterministic FPGA safety logic with local edge intelligence. The reference design observes machine condition, detects abnormal behavior, estimates developing faults, and requests bounded automation while preserving a hard real-time safety path that does not depend on ML inference or network availability.

> **Project status:** Active pre-hardware implementation. The repository contains an executable digital reference, a versioned bidirectional FPGA/ESP32-S3 link, a host-tested embedded inference implementation, deterministic VHDL control logic, persistent event-record infrastructure, and multi-scenario closed-loop validation.

## Why ForgeSense AI

The system is built around a strict separation of authority:

- the FPGA owns deterministic timing, hard limits, emergency behavior, watchdogs, interlocks, state transitions, and final output authority;
- the ESP32-S3 receives normalized sensor snapshots, performs bounded edge inference, and returns versioned health observations;
- accepted intelligence can influence only documented FPGA state transitions and cannot override hard safety rules;
- communication corruption, replay, stale inference, sensor invalidity, or loss of the edge processor produce deterministic behavior;
- the same wire contracts are shared by simulation, host tests, embedded firmware, and synthesizable RTL;
- offline operation, low cost, inspectability, and reproducibility are first-class constraints.

The project does **not** claim unverified uniqueness, patentability, or industrial certification. Technical novelty and protectable work require documented prior-art and legal review before public claims are made.

## Current End-to-End Architecture

```text
Temperature / vibration / current inputs
                |
                v
      FPGA sensor normalization
                |
                v
     ForgeSense Link SENSOR frame
                |
                v
          UART 8N1 transport
                |
                v
        ESP32-S3 link service
                |
                v
       8-sample feature window
                |
                v
       compact edge inference
                |
                v
       ForgeSense Link ML frame
                |
                v
       UART -> FPGA receiver
                |
                v
 CRC + version + type + model/schema + age + sequence checks
                |
                v
       latched accepted ML state
                |
                +---------------------------+
                v                           |
      deterministic safety FSM             |
                |                           |
        hard limits / emergency <-----------+
                |
                v
        protected load enable
```

The FPGA sends normalized sensor snapshots at a configured sampling rate and emits deterministic safety-status snapshots periodically and on state changes. The ESP32-S3 maintains a fixed-size feature window, performs local inference, and returns a bounded ML observation. The FPGA validates every received observation before it can affect control state. Accepted health state is retained until replaced by a newer accepted observation; missing, invalid, replayed, or corrupt traffic never clears it.

## Safety Invariants

- Hard critical conditions and emergency input take priority over ML.
- Sensor invalidity fails closed through the deterministic hard-fault path.
- ML warm-up cannot cause a premature communication timeout.
- Only fresh, compatible, CRC-valid ML observations reset the intelligence watchdog.
- Replayed or duplicate observations cannot keep the system operational.
- A critical first operational observation goes directly to shutdown; the load is never transiently enabled.
- An accepted warning remains active until a newer accepted observation clears it or another safety condition takes precedence.
- Wi-Fi, dashboard, telemetry, or storage failure cannot become the sole safety path.

ForgeSense AI remains a research and engineering platform, not a certified industrial safety controller. Experimental validation must use current-limited, low-voltage loads until the electrical design and hazard controls are independently validated.

## Repository Layout

```text
ForgeSense-AI/
├── fpga/                 # VHDL UART, sensing, protocol, safety and board-level core
├── firmware/             # ESP32-S3 application + portable C++ components
├── ml/                   # reference model, export and edge-runtime behavior
├── simulator/            # deterministic plant, scenarios and safety oracle
├── protocol/             # ForgeSense Link wire specification and Python reference
├── tests/                # software and cross-language regression tests
├── tools/                # demos, validation and model export utilities
├── hardware/             # schematic/PCB evidence as physical design is finalized
├── dashboard/            # local monitoring UI as the telemetry interface matures
├── docs/                 # engineering source of truth
└── .github/              # repository and implementation checks
```

## ForgeSense Link v1

The reference uses one full-duplex UART connection with independent rolling sequence spaces in each direction.

| Direction | Message | Type | Frame size |
| --- | --- | ---: | ---: |
| FPGA -> ESP32-S3 | Sensor snapshot | `0x11` | 22 bytes |
| FPGA -> ESP32-S3 | Safety status snapshot | `0x30` | 18 bytes |
| ESP32-S3 -> FPGA | ML observation | `0x10` | 28 bytes |

Both frames use `A5 5A` framing, protocol versioning, explicit payload length, sender monotonic timestamp, and CRC-16/CCITT-FALSE. The sensor frame carries signed temperature, vibration RMS, current, and per-sensor validity flags. The ML frame carries model identity, model version, feature-schema version, anomaly score, health class, confidence, and inference age.

See [`protocol/SPEC_V1.md`](protocol/SPEC_V1.md).

## Reference ML Model

The current model is deliberately small and auditable: a diagonal-Gaussian anomaly baseline fitted over the complete settled normal operating envelope after the first 80 synthetic samples. The same parameters are exported deterministically into a generated C++ header used by the embedded reference runtime.

This model is an integration baseline, not a claim of production predictive-maintenance accuracy. Real hardware data, grouped/time-aware evaluation, drift testing, false-alarm measurement, and model comparison are required before such claims.

Regenerate and verify the embedded model constants:

```bash
make model-export
```

## ESP32-S3 Runtime

`firmware/esp32` is an ESP-IDF application scaffold with:

- configurable UART port, TX/RX GPIOs and baud rate;
- fixed-memory sensor stream decoding and sequence freshness checks;
- invalid-sensor feature-window reset;
- host-tested edge inference component;
- ML frame encoding and UART transmission;
- link-loss detection;
- transition-based ML warning/critical event records;
- CRC-protected fixed-size persistent event records stored in an NVS ring.

The portable C++ protocol, stream, inference, and event components are host tested without requiring an ESP32 board. The complete ESP-IDF application must still be built and hardware-tested with the selected ESP32-S3 target before it is considered device-validated.

## FPGA Runtime

The VHDL reference now includes:

- millisecond timebase and configurable sensor sample scheduler;
- 8N1 UART receiver and transmitter;
- sensor validity normalization;
- 22-byte sensor-frame transmitter;
- 28-byte ML-frame receiver;
- CRC-16 validation;
- compatibility, freshness and replay gate;
- persistent accepted ML health state;
- hard-limit monitor;
- supervised communication watchdog;
- deterministic safety FSM;
- board-level integration core.

The default board-facing clock profile is 27 MHz with 115200-baud UART and a 10 Hz sensor snapshot rate. These defaults are engineering placeholders until the physical FPGA board and electrical interfaces are frozen.

## Current Validation Evidence

The software reference currently passes eleven Python regression tests and four host C++ executables. The deterministic scenario matrix is:

| Scenario | Injected at | First warning | Terminal action | Hard critical at terminal |
| --- | ---: | ---: | --- | --- |
| Normal | - | - | none | - |
| Bearing degradation | 220 | 238 | shutdown at 240 | no |
| Overcurrent trend | 180 | 240 | shutdown at 248 | no |
| Cooling loss | 260 | 391 | shutdown at 521 | no |
| Sensor dropout | 180 | - | fault-latched at 180 | yes |
| Intelligence link loss | 180 | - | watchdog shutdown at 194 | no |
| Emergency | 180 | - | fault-latched at 180 | no |

These are deterministic virtual-reference results only. They demonstrate system behavior and interface correctness, not real-machine detection performance.

Run the matrix:

```bash
make validate
```

## Development Commands

```bash
make test
make demo
make closed-loop
make validate
make model-export
make firmware-host
```

`make firmware-host` compiles portable embedded components with C++20, `-Wall -Wextra -Werror -pedantic` and executes protocol, stream, inference, and event-record tests.

## Hardware Boundary

The first physical reference remains intentionally low voltage. The planned board path is:

```text
low-voltage machine/load
        |
temperature / vibration / current sensing
        |
input protection and conditioning
        |
FPGA deterministic domain <----UART----> ESP32-S3 edge domain
        |
protected MOSFET/driver abstraction
        |
controlled low-voltage load
```

Exact FPGA device, sensors, analog front end, output driver, protection network, PCB stack-up, connectors, and power tree are not frozen until the electrical requirements are validated.

## Documentation

Start at [`docs/README.md`](docs/README.md). Important implementation documents include:

- [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md)
- [`docs/TRANSPORT_AND_CONTROL.md`](docs/TRANSPORT_AND_CONTROL.md)
- [`docs/SENSOR_ACQUISITION.md`](docs/SENSOR_ACQUISITION.md)
- [`docs/FIRMWARE.md`](docs/FIRMWARE.md)
- [`docs/EVENT_RECORDS.md`](docs/EVENT_RECORDS.md)
- [`docs/VALIDATION_MATRIX.md`](docs/VALIDATION_MATRIX.md)
- [`docs/SAFETY_MODEL.md`](docs/SAFETY_MODEL.md)
- [`docs/VERIFICATION.md`](docs/VERIFICATION.md)

## Contributing, Security and IP

Read [`CONTRIBUTING.md`](CONTRIBUTING.md), [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md), and [`SECURITY.md`](SECURITY.md) before proposing changes. Do not disclose suspected vulnerabilities in public issues.

The repository remains under an **all-rights-reserved development license** while architecture, prior art, publication strategy, and potentially protectable work are evaluated. See [`LICENSE`](LICENSE) and [`docs/IP_AND_PUBLICATION.md`](docs/IP_AND_PUBLICATION.md).

## Author

**Md Shahanur Islam Shagor**  
Full-Stack Web Developer & AI / Autonomous Systems Engineer  
GitHub: [@smshagor-dev](https://github.com/smshagor-dev)

---

ForgeSense AI is built as an engineering system first: every intelligent behavior is bounded, every safety behavior is testable, and every hardware decision must be justified by measurable evidence.
