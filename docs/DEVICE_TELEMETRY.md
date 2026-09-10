# ESP32-S3 Device Telemetry

## Purpose

This interface carries read-only engineering observations from the ESP32-S3 to a host computer so the local ForgeSense monitor can display real FPGA state, sensor values, edge inference and link diagnostics without introducing a control path.

The FPGA remains the authoritative source for machine state and protected-output behavior. Device telemetry is observational only.

## Record format

The ESP32-S3 emits one UTF-8 JSON object per line with the prefix:

```text
@FS1 
```

The current schema identifier is:

```text
forgesense.edge.telemetry.v1
```

Records contain optional `sensor`, `fpga_status`, and `ml` snapshots plus link counters. Numeric sensor and inference values use protocol-native integer units rather than floating-point text:

- temperature: deci-degrees Celsius;
- vibration RMS: milli-g;
- current: milliamps;
- anomaly: unsigned Q15 in `0..32767`;
- confidence: unsigned Q8 in `0..255`.

Every source snapshot includes its protocol sequence, sender timestamp and age measured on the ESP32-S3 when the host record is emitted.

## Freshness and authority

A host must never turn stale device data into apparently fresh control state merely by receiving a newer telemetry line. The Python device bridge therefore rejects a section whose device-reported `received_age_ms` exceeds the configured freshness threshold.

In particular, stale or missing FPGA status means the monitoring API reports machine state as `UNKNOWN`. Sensor or ML fields may remain visible independently, but neither substitutes for authoritative FPGA status.

## Physical host transport

The first hardware profile routes device telemetry through the ESP-IDF standard console, separate from the FPGA UART. On ESP32-S3 boards that expose the built-in USB Serial/JTAG path, that console can provide the host serial stream without adding a network dependency. Boards using another console route can carry the same records over a separate USB-UART channel.

Normal ESP-IDF log lines may share the host console. The ForgeSense host bridge ignores any line that does not start with `@FS1 `.

The FPGA control UART must not be reused as the host telemetry channel.

## Host bridge

Install the optional serial dependency and run:

```bash
python -m pip install -r requirements-device.txt
PYTHONPATH=simulator:ml:protocol/python:telemetry python tools/run_dashboard_device.py --device-port COM8
```

Linux device names such as `/dev/ttyACM0` are also accepted. For captured console output or piping from another trusted serial utility, use `--stdin`.

The resulting HTTP surface is the same local read-only monitoring API used by the simulation dashboard. It exposes no actuator, reset or recovery operation.

## Embedded publisher behavior

The firmware publisher uses fixed-capacity serialization and does not allocate an unbounded telemetry buffer. It emits periodically and may force an immediate snapshot on important transitions such as FPGA state change, hard-critical/emergency assertion, sensor-validity loss or link recovery/loss.

Telemetry failure must not alter FPGA communication, inference, hard safety behavior or protected-output state.

## Security boundary

This transport is diagnostic, not authenticated command transport. Do not add command parsing to the `@FS1` channel. Any future remote-management design requires a separate protocol, explicit authorization model, replay protection and safety review.
