# Selected Sensor Behavioral Verification

## Purpose

This verification layer exercises the selected TMP117, ADXL355, and ADS131M02 FPGA controllers against bus-level device models before physical hardware is available. The models connect to the same I2C and SPI pins used by the controller RTL; they do not bypass controller state machines or inject normalized values directly into the safety core.

The goal is to catch transaction-order, identity, configuration-readback, framing, CRC, conversion, and fault-propagation defects early. It is still pre-hardware evidence and does not replace bench measurements.

## TMP117 model

`fpga/tb/models/tmp117_i2c_model.vhd` implements the controller-visible TMP117 transaction subset:

- 7-bit address `0x48`;
- register-pointer write followed by repeated START;
- Device ID register `0x0F` with expected value `0x0117`;
- temperature result register `0x00`;
- two-byte read with master ACK then NACK;
- explicit address/register ACK behavior;
- forced NACK injection;
- wrong-identity injection.

`tb_tmp117_controller_behavioral.vhd` proves the normal identity/temperature path and rejects both a wrong identity and a bus NACK. The reference temperature raw code `0x0C80` must publish 25.0 degrees C as `250` deci-degrees C.

## ADXL355 model

`fpga/tb/models/adxl355_spi_model.vhd` implements the selected SPI mode-0 register behavior:

- `DEVID_AD`, `DEVID_MST`, and `PARTID` identity registers;
- FILTER, RANGE, and POWER_CTL writes and readback;
- auto-increment X/Y/Z burst reads from `XDATA3`;
- signed 20-bit axis payloads;
- wrong-identity injection;
- corrupted configuration-readback injection.

`tb_adxl355_controller_behavioral.vhd` verifies startup configuration, a DRDY-triggered three-axis burst, positive/negative fixed-point conversion, identity rejection, and configuration-readback rejection.

## ADS131M02 model

`fpga/tb/models/ads131m02_spi_model.vhd` implements the selected CPOL=0/CPHA=1 controller-visible behavior:

- 12-byte frames representing four 24-bit words;
- delayed single-register response behavior used by RREG;
- ID response with fixed high byte `0x22`;
- CLOCK register write and later readback;
- conversion frames containing STATUS, CH0, CH1, and output CRC;
- CRC-16/CCITT calculation using polynomial `0x1021` and seed `0xFFFF`;
- wrong-identity injection;
- corrupted CLOCK readback injection;
- corrupted output-CRC injection.

`tb_ads131m02_controller_behavioral.vhd` proves the startup command sequence, CLOCK readback, valid conversion publication, CRC rejection, identity rejection, and configuration-readback rejection.

## Combined acquisition cluster

`tb_selected_sensor_cluster_behavioral.vhd` runs all three selected devices together on one FPGA clock. Each controller communicates with its own bus-level model, reaches its trusted configuration state, and publishes a deterministic sample.

The combined test verifies:

- TMP117 publishes 25.0 degrees C;
- ADXL355 publishes the expected conditioned axis values;
- ADS131M02 publishes the expected STATUS and 24-bit channel values;
- all three identity/configuration states remain trusted after valid acquisition.

This test intentionally stops at the selected acquisition cluster. Hard limits, watchdog behavior, ML freshness, UART framing, output gating, and independent analog/E-stop paths remain covered by their dedicated verification suites.

## Automated checks

`tools/check_sensor_behavioral_verification.py` verifies that the required model files, fault controls, test suites, and critical assertions remain present.

`.github/workflows/sensor-behavioral.yml` is a dedicated GHDL workflow that:

1. validates the behavioral-verification inventory;
2. analyzes the selected serial engines, conversion package, device controllers, device models, and testbenches;
3. elaborates and runs all four self-checking testbenches with assertion failures treated as errors.

## Evidence boundary

Passing these simulations can support claims about controller transaction logic and the modeled fault cases only. It cannot establish:

- real I2C rise/fall timing or pull-up margin;
- SPI signal integrity, skew, ringing, or crosstalk;
- ADS131M02 analog accuracy, noise, reference behavior, or real CRC behavior under electrical disturbance;
- ADXL355 mounting transfer function, mechanical resonance, bandwidth, or orientation;
- TMP117 placement error, board heating, or thermal lag;
- EMC immunity;
- final FPGA timing closure and resource utilization;
- machine-specific safety limits or functional-safety certification.

Those require physical bring-up, retained measurements, and the applicable qualification process.
