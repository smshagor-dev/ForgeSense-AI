# Physical Commissioning Utility

## Purpose

The commissioning utility turns the physical bring-up procedure into repeatable serial measurements without giving the PC monitoring path actuator authority.

It has two operating modes:

- `smoke`: validates the reduced-authority FPGA smoke image by observing `0x55` heartbeats and sending stop-and-wait echo bytes;
- `observe`: passively decodes production FPGA STATUS and sensor frames and never writes to the FPGA link.

The preferred development path uses the separate ESP32-S3 commissioning bridge image, so the test traverses the real Tang Nano 9K <-> ESP32-S3 GPIO17/18 harness rather than bypassing it with a separate USB-UART adapter.

## ESP32-S3 commissioning bridge

Project:

`firmware/esp32_commissioning`

The bridge has exactly two data paths:

```text
PC USB Serial/JTAG -> ESP32-S3 -> UART1 GPIO17 -> Tang Nano FPGA RX
PC USB Serial/JTAG <- ESP32-S3 <- UART1 GPIO18 <- Tang Nano FPGA TX
```

The bridge does not initialize Wi-Fi, NVS, ML, telemetry, or actuator-control logic. It uses the ESP32-S3 USB Serial/JTAG driver as a raw byte transport and keeps the normal console/log output disabled so commissioning bytes are not mixed with log text.

Reference build flow with an ESP-IDF environment:

```bash
cd firmware/esp32_commissioning
idf.py set-target esp32s3
idf.py build
idf.py -p PORT flash
```

A successful ESP-IDF target build/flash remains physical/tool evidence and must not be inferred from the source files alone.

## Host installation

The core commissioning library and tests use only the Python standard library plus the existing ForgeSense protocol modules. Physical serial access uses the optional `pyserial` dependency:

```bash
python -m pip install -e '.[commissioning]'
```

For repository-source execution without installing the package:

```bash
PYTHONPATH=protocol/python:commissioning python -m forgesense_commission --help
```

## Smoke commissioning

Program the Tang Nano smoke image first. Confirm the motor stage remains physically inhibited as described in `PHYSICAL_BRINGUP.md`.

Then run through the ESP32-S3 commissioning bridge COM/tty port:

```bash
PYTHONPATH=protocol/python:commissioning \
python -m forgesense_commission \
  --port PORT \
  smoke \
  --heartbeats 2 \
  --report-out build/smoke_report.json
```

The default echo vector is:

```text
A6 3C 81 00 FE
```

The utility records:

- observed idle heartbeat count;
- bytes transmitted;
- successful echoes;
- timeouts;
- error rate;
- min/mean/max measured host round-trip latency;
- unexpected non-heartbeat bytes.

Heartbeat or echo failure returns a non-zero exit code.

The smoke utility does not prove `LOAD_ENABLE` is electrically low. That remains a DMM/logic-analyzer bench check and must remain `NOT_RUN` until physically measured.

## Production observation

After the production Tang image and selected sensors are connected, passive observation is:

```bash
PYTHONPATH=protocol/python:commissioning \
python -m forgesense_commission \
  --port PORT \
  observe \
  --duration 5 \
  --report-out build/production_observation.json
```

`observe` does not call the transport write path. It decodes:

- valid STATUS frame count;
- valid sensor snapshot count;
- stream framing/CRC errors;
- FPGA safety state;
- load/warning/fault/ready state;
- required-sensor validity;
- selected-device identity/configuration status;
- selected-device/PHY transport-error status;
- latest normalized temperature, vibration RMS, and current.

The selected-device diagnostic fields come from STATUS safety bits 7 and 8. They are FPGA observations only and do not change safety authority.

## Bench-record auto-population

A report can be generated without evidence metadata. A bench record cannot.

When `--record-out` is requested, all of the following must be supplied with real values:

- record ID;
- operator;
- exact 40-hex repository commit;
- exact programmed-artifact SHA-256;
- FPGA board revision;
- sensor-board revision.

Example:

```bash
PYTHONPATH=protocol/python:commissioning \
python -m forgesense_commission \
  --port PORT \
  smoke \
  --record-out evidence/bringup-smoke-001.json \
  --record-id BRINGUP-SMOKE-001 \
  --operator 'LAB_OPERATOR' \
  --repository-commit 0123456789abcdef0123456789abcdef01234567 \
  --artifact-sha256 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
  --fpga-board-revision REVISION \
  --sensor-board-revision REVISION
```

Serial-measured checks are updated automatically. Checks that require a DMM, oscilloscope, continuity meter, or physical inspection remain `NOT_RUN` until separately recorded.

Validate any retained bench record with:

```bash
make bench-record-validate RECORD=path/to/record.json
```

## Status diagnostic extension

ForgeSense Link v1 STATUS remains an 18-byte frame with a 4-byte payload. Two previously reserved safety bits are now assigned:

- bit 7 / `0x0080`: selected TMP117 + ADXL355 + ADS131M02 identity/configuration checks all succeeded;
- bit 8 / `0x0100`: selected-device or normalized PHY transport/conditioning error observed.

Older receivers that ignore unknown safety bits remain frame-compatible.

## Verification

Run the source-level commissioning gate with:

```bash
make commissioning-check
```

It covers:

- fake-serial smoke heartbeat/echo behavior;
- automatic bench-record updates without inventing manual evidence;
- mixed STATUS/sensor stream decoding;
- selected-device diagnostics;
- cross-language Python/C++ bit masks;
- C++ parsing of a diagnostic STATUS golden frame;
- VHDL diagnostic propagation source contract;
- ESP32-S3 raw bridge GPIO/USB transport contract;
- read-only production observation invariant.

Physical USB/UART timing, ESP-IDF target build success, and real bench measurements remain unclaimed until retained evidence exists.
