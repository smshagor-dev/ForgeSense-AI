# ESP32-S3 Firmware

## Role

The ESP32-S3 hosts edge feature extraction, compact inference, FPGA link transport, local persistence, and later telemetry services. It is outside the hard safety trust boundary and never directly owns the protected output.

## Current implementation

The repository contains an ESP-IDF application under `firmware/esp32` and portable host-tested components under `firmware/components`.

```text
firmware/
├── esp32/
│   ├── CMakeLists.txt
│   ├── sdkconfig.defaults
│   └── main/
│       ├── app_main.cpp
│       ├── link_service.*
│       ├── event_store_nvs.*
│       └── Kconfig.projbuild
├── components/
│   ├── forgesense_protocol/
│   ├── forgesense_inference/
│   └── forgesense_events/
└── tests/
```

## Runtime data path

```text
FPGA sensor snapshot
        ↓
UART RX
        ↓
CRC/type/length decoder
        ↓
sensor sequence gate
        ↓
validity gate
        ↓
8-sample feature window
        ↓
compact anomaly inference
        ↓
bounded ML observation
        ↓
UART TX -> FPGA
```

Invalid required sensors clear the feature window. Duplicate or backwards sensor sequence values are rejected before inference.

## Model binding

The committed synthetic reference model is generated from the complete settled normal simulation envelope. `tools/export_reference_model.py` emits the C++ constants, and automated tests verify the committed header is reproducible from the Python model. This prevents firmware constants from drifting away from evaluated model parameters.

The synthetic reference model is not hardware calibrated. Physical data must replace its parameters before performance claims are made.

## Local event persistence

Critical state changes are encoded as fixed-size CRC-protected records and stored in an NVS ring. The default ring contains 64 slots and is configurable. Boot, sensor invalidity, local link loss/recovery, and ML warning/critical transitions are recorded.

Normal high-rate telemetry is not written on every sample; the NVS path is for sparse diagnostic evidence, reducing unnecessary flash wear. Persistence never substitutes for FPGA safety state.

## Configurable board settings

ESP-IDF configuration exposes the FPGA link UART port, TX/RX GPIOs, UART baud rate, event-ring size, and local sensor-link-loss interval. Defaults are development values and must be checked against the selected board and schematic.

## Firmware invariants

- Parse and validate before use.
- Reject unsupported protocol versions and lengths.
- Reject duplicate/backwards sensor sequences.
- Keep model ID, model version, and feature schema bound together.
- Reset the feature window on invalid required input.
- Never translate dashboard/network input into unrestricted FPGA output control.
- Make reset/link loss visible through deterministic FPGA communication behavior.
- Persist sparse diagnostic events with integrity metadata.
- Keep Wi-Fi optional for local sensing and inference.

## ESP-IDF build

With a supported ESP-IDF environment:

```bash
cd firmware/esp32
idf.py set-target esp32s3
idf.py build
```

Pin assignment and electrical validation are not final until the selected development board and circuit revision are frozen.

## Deterministic FPGA status feedback

The edge runtime consumes FPGA `STATUS` frames separately from sensor snapshots. It records transitions for hard-critical, emergency, and recovery conditions while keeping those records diagnostic-only. Sensor and status streams have independent sequence gates. A fixed-capacity pending queue preserves multiple fresh FPGA frames decoded from one UART receive chunk; overflow is observable through a counter and drops the oldest pending diagnostic message in favor of newer state.
