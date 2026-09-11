# Calibration Diagnostic Stream

## Purpose

ForgeSense uses a dedicated Tang Nano 9K calibration image to expose measured sensor data to the bench PC without enabling the external load or changing production safety behavior.

The path is:

```text
TMP117 / ADXL355 / ADS131M02
        |
        v
Tang Nano 9K calibration image
        |
        | ForgeSense read-only diagnostic frame 0x32
        v
ESP32-S3 commissioning bridge
        |
        | transparent USB Serial/JTAG byte forwarding
        v
forgesense_commission calibration
        |
        v
JSON evidence capture
```

The ESP32-S3 commissioning image remains a transparent bridge. It does not interpret or modify diagnostic frames.

## Authority boundary

`forgesense_tang_nano_9k_calibration_top` is intentionally not a control image.

Its external load output is fixed to:

```text
load_enable_o = 0
```

The image contains no UART command receiver, ML observation path, recovery command handling, safety-state control path, or actuator authorization logic.

The host capture artifact likewise declares:

```text
read_only = true
may_control_actuators = false
may_apply_calibration = false
may_relax_hard_safety_limits = false
```

Captured values are evidence only. They are not written back to FPGA or ESP32 runtime configuration.

## Diagnostic frame

The diagnostic message type is `0x32`. It uses the standard ForgeSense Link framing and CRC-16/CCITT-FALSE rules, but it is reserved for the bench calibration image rather than the production application contract.

The full frame is 30 bytes:

| Bytes | Field | Encoding |
| --- | --- | --- |
| 0-1 | SOF | `A5 5A` |
| 2 | protocol version | `01` |
| 3 | message type | `32` |
| 4-5 | sequence | little-endian `uint16` |
| 6-7 | payload length | `0x0010` |
| 8-11 | FPGA monotonic timestamp | little-endian `uint32` ms |
| 12-14 | ADS131M02 channel 0 raw | signed 24-bit little-endian |
| 15-17 | ADS131M02 channel 1 raw | signed 24-bit little-endian |
| 18-19 | TMP117 temperature | signed `int16`, deci-degrees C |
| 20-21 | ADXL355 X | signed `int16`, milli-g |
| 22-23 | ADXL355 Y | signed `int16`, milli-g |
| 24-25 | ADXL355 Z | signed `int16`, milli-g |
| 26-27 | diagnostic flags | little-endian `uint16` |
| 28-29 | CRC | little-endian CRC-16/CCITT-FALSE over bytes 2-27 |

## Diagnostic flags

| Bit | Meaning |
| --- | --- |
| 0 | at least one TMP117 sample has been observed since reset |
| 1 | at least one ADXL355 sample has been observed since reset |
| 2 | at least one ADS131M02 sample has been observed since reset |
| 3 | TMP117 identity/configuration is trusted |
| 4 | ADXL355 identity/configuration is trusted |
| 5 | ADS131M02 identity/configuration is trusted |
| 6 | TMP117 transport error has been observed since reset |
| 7 | ADXL355 initialization/transport error has been observed since reset |
| 8 | ADS131M02 frame/CRC error has been observed since reset |
| 9-15 | reserved, zero |

A sample is usable for calibration only when all three sample-seen bits and all three device-trusted bits are set and none of the error bits are set.

## FPGA build

With Gowin EDA available:

```bash
gw_sh fpga/scripts/tang_nano_9k_calibration_build.tcl
```

or:

```bash
make calibration-build
```

The calibration build reuses the frozen Tang Nano 9K pin constraints. It instantiates the selected TMP117, ADXL355, and ADS131M02 device controllers plus the dedicated diagnostic transmitter and UART TX path.

No successful Gowin place-and-route or physical-board result is claimed until retained tool output exists.

## ESP32-S3 bridge

Flash the existing bench-only bridge under `firmware/esp32_commissioning/`. It forwards the FPGA UART stream to the PC through USB Serial/JTAG without adding text logging or control behavior.

The calibration image transmits diagnostics at a low bounded rate so the 115200-baud bridge has ample framing margin.

## Capture on the PC

Install the device dependency and run:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python -m forgesense_commission \
  --port /dev/ttyACM0 \
  calibration \
  --duration 10 \
  --report-out evidence/calibration-diagnostic-run-01.json
```

On Windows, replace `/dev/ttyACM0` with the actual COM port, for example `COM7`.

The output schema is:

```text
forgesense.calibration_diagnostic_capture.v1
```

It contains every retained diagnostic sample, sequence-integrity results, CRC/frame error counts, the latest sample, and explicit read-only authority metadata.

The command exits successfully only when at least one trusted, complete sample was captured with no sequence gap/fault and no CRC/frame error.

## Relationship to calibration proposals

The diagnostic capture is raw bench evidence. It does not know the independently measured reference current or reference temperature.

For a real calibration run:

1. Capture the FPGA diagnostic stream for each controlled operating point.
2. Retain the diagnostic JSON and calculate its SHA-256.
3. Record the independent reference current/temperature and instrument uncertainty in the calibration-capture artifact.
4. Use the ADS131M02 channel-0 raw values and trusted sensor readings to populate the evidence-backed calibration capture.
5. Generate a review-only proposal with `tools/capture_calibration.py`.
6. Repeat the run at least three times and use `tools/review_calibration.py` before considering any source-controlled coefficient change.

Do not derive reference truth from the same ForgeSense sensor being calibrated.

## Verification

Run:

```bash
make calibration-diagnostic-check
```

This verifies the Python decoder/collector, signed 24-bit handling, sequence rejection behavior, device-error rejection, host authority metadata, and source-level FPGA safety boundary.

The CI workflow also analyzes the calibration VHDL image and runs `tb_calibration_diag_tx`, which checks the message type, payload length, little-endian field packing, signed values, flags, and CRC.
