# Selected Sensor Device Drivers

## Purpose

This document records the first register-level FPGA acquisition implementation for the selected ForgeSense reference sensors. The implementation remains pre-hardware: register contracts and transport behavior are derived from manufacturer documentation, while electrical timing, signal integrity, calibration accuracy, mounting, and physical fault behavior still require bench evidence.

## Transport split

The selected devices do not share one generic serial timing mode.

- TMP117 uses I2C at a requested maximum of 400 kHz.
- ADXL355 uses SPI mode 0 (CPOL=0, CPHA=0) at a requested maximum of 2 MHz.
- ADS131M02 uses CPOL=0/CPHA=1 behavior for DIN/DOUT timing and therefore uses a separate mode-1 byte engine at a requested maximum of 2 MHz.

All FPGA serial dividers use ceiling division. If 27 MHz cannot divide exactly to the requested bus frequency, the generated frequency is rounded downward, never upward beyond the configured maximum.

## TMP117

`fpga/rtl/sensing/tmp117_controller.vhd` performs an automatic identity probe after reset.

Reference contract:

- 7-bit address: `0x48` with ADD0 tied to GND;
- temperature result register: `0x00`;
- device ID register: `0x0F`;
- expected device ID: `0x0117`;
- temperature LSB: 0.0078125 degrees C.

A measurement uses START, write-address, register-pointer, repeated START, read-address, high-byte read with ACK, low-byte read with NACK, and STOP. A NACK is surfaced as a transport error. Raw signed temperature is converted deterministically to deci-degrees C.

## ADXL355

`fpga/rtl/sensing/adxl355_controller.vhd` validates the selected accelerometer before publishing samples.

Startup sequence:

1. read DEVID_AD and require `0xAD`;
2. read DEVID_MST and require `0x1D`;
3. read PARTID and require `0xED`;
4. write FILTER = `0x02` for the 1 kHz reference output-data rate;
5. write RANGE = `0x03` for the +/-8 g reference range;
6. write POWER_CTL = `0x00` for measurement operation;
7. read configuration back before asserting `device_ok`.

A DRDY rising edge starts one 9-byte burst from XDATA3. The three signed 20-bit left-justified axis samples are converted to milli-g using the +/-8 g sensitivity reference. The current reference wrapper feeds the Z-axis into the existing vibration-conditioning/RMS path; future physical characterization may choose a different axis or vector feature without changing the hard-safety authority model.

## ADS131M02

`fpga/rtl/sensing/ads131m02_controller.vhd` uses the selected ADC's 24-bit four-word output frame:

1. response/status word;
2. channel 0 conversion;
3. channel 1 conversion;
4. mandatory output CRC word.

The controller reads exactly 12 bytes per frame. The CRC-16/CCITT calculation uses polynomial `0x1021` and seed `0xFFFF`; conversion data are published only after CRC validation.

Startup sequence:

1. send single-register RREG for ID (`0xA000`);
2. validate the register value returned in the next frame; bits 15:8 must be `0x22`, while the reserved low byte is not treated as a fixed identity value;
3. write CLOCK register using WREG `0x6180` with value `0x0316`;
4. issue RREG CLOCK (`0xA180`);
5. validate `0x0316` in the following frame before asserting `device_ok`.

The `0x0316` reference selects both channels, high-resolution power mode and the OSR reference used for the 1 kSPS target with the 8.192 MHz master clock. Normal NULL-command frames are accepted by CRC; the response word is treated as STATUS, not as a substitute for reading MODE/WLENGTH configuration.

## Current-input correction

The selected ADC forced an important correction to the analog baseline. The former 25 mOhm shunt with 20 V/V current-sense gain produced 1.60 V at 3.2 A, exceeding the ADS131M02 gain-1 nominal differential full scale of +/-1.2 V.

The current reference is now:

```text
Rshunt = 15 mOhm
INA181A1 gain = 20 V/V
Ireference = 3.2 A
Vshunt = 0.048 V
CS_OUT = 0.960 V
ADC nominal FSR utilization = 80 percent
```

The independent comparator divider was revised to 23.2 kOhm / 10.7 kOhm, producing approximately 1.042 V and an ideal analog trip near 3.47 A. The analog trip remains below the approximately 4.04 A input eFuse reference and the 5 A passive fuse.

## Selected-device composition

`fpga/rtl/top/forgesense_reference_sensor_io.vhd` composes the three selected device controllers with the existing normalized sensor frontend and deterministic safety core.

- TMP117 produces normalized temperature updates.
- ADS131M02 channel 0 is converted from signed 24-bit ADC code to current in mA using the revised analog transfer.
- ADXL355 Z-axis samples feed the fixed-window vibration path.
- identity/configuration errors and transport/CRC faults prevent the affected source from being treated as a healthy measurement stream.

The ESP32-S3 and ML path do not gain authority over these acquisition or hard-safety checks.

## Verification boundary

Executable repository checks validate register constants, current-transfer arithmetic, bus-divider direction, source contracts, and the reusable SPI transport. CI is configured to analyze the selected controllers and composed wrapper with GHDL when a hosted runner is actually allocated.

Still requiring physical evidence:

- sensor identity and configuration on real devices;
- SPI/I2C rise/fall timing and signal integrity;
- ADS131M02 CRC behavior under measured transactions;
- analog gain/offset and shunt calibration;
- ADXL355 mounting, axis selection and vibration bandwidth;
- TMP117 placement/thermal lag;
- electromagnetic interference and motor-switching susceptibility;
- final FPGA timing closure and resource use.
