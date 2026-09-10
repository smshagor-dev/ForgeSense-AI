# Sensor Acquisition Contract

## Purpose

ForgeSense separates physical sensor drivers from the normalized safety/ML interface. Driver-specific logic may change with the selected temperature, vibration, or current device, but every driver must produce the same normalized channel contract before its data enters the rest of the system.

The source of truth is `hardware/profiles/sensor_contract_v1.json`. Generated C++ and VHDL constants are committed and regression-checked so host, embedded, and FPGA code do not silently drift.

## Normalized channels

| Channel | Wire unit | Development plausibility range | Freshness limit |
| --- | --- | ---: | ---: |
| Temperature | deci-degrees Celsius | -40.0 to 125.0 C | 1000 ms |
| Vibration | milli-g RMS | 0 to 16,000 mg RMS | 500 ms |
| Current | milliamps | 0 to 20,000 mA | 500 ms |

All three channels are required in contract version 1. The limits above are data-quality guards for development; they are **not** certified machine protection thresholds.

## Vibration boundary

The normalized vibration channel is an RMS feature. A physical accelerometer normally needs a substantially higher raw sampling rate than the 10 Hz ForgeSense snapshot publication rate. The future device-specific vibration driver must acquire an adequate raw window, remove/handle bias as required, compute the documented RMS feature, and only then assert a normalized update.

This keeps raw sensor bandwidth decisions out of the FPGA/ESP32 application protocol.

## FPGA freshness supervisor

`sensor_supervisor.vhd` receives normalized channel updates and records the local FPGA millisecond timestamp of each accepted update. A channel is valid only when:

- at least one update has been seen since reset;
- the most recent value is inside the configured plausibility range; and
- the update age is within that channel's freshness limit.

A stale or implausible required channel deasserts aggregate `sensors_valid`. Fresh plausible data can recover the channel. Unsigned timestamp subtraction preserves correct age calculation across 32-bit millisecond wrap.

## Generation

Regenerate the shared constants with:

```bash
python tools/generate_sensor_contract.py hardware/profiles/sensor_contract_v1.json \
  --cxx firmware/components/forgesense_protocol/include/forgesense_sensor_contract_generated.h \
  --vhdl fpga/rtl/sensing/sensor_contract_pkg.vhd
```

Automated tests require regenerated output to be byte-for-byte identical to the committed files.

## Hardware status

No exact sensor model, ADC transfer function, analog front-end, accelerometer full-scale, anti-alias filter, or calibration coefficient is frozen by this contract. Those values require the selected components, schematic, and measured calibration evidence.
