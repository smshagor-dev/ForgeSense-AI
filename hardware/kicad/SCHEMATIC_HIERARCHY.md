# ForgeSense AI Schematic Hierarchy

The first custom carrier/control board is organized as a hierarchical KiCad design. Sheet names and net names are frozen here before graphical capture begins.

## Sheets

1. `00_root` — hierarchical interconnect, board revision, test points and global power/safety nets.
2. `01_input_protection` — 12 V input, fuse, reverse-polarity protection, TVS footprint and bulk filtering.
3. `02_power` — protected 12 V branch, 5 V regulator, 3.3 V regulator, rail test points and decoupling.
4. `03_compute` — Tang Nano 9K headers/module interface and ESP32-S3 DevKitC-1 headers/module interface.
5. `04_current_sense` — 25 mOhm Kelvin shunt, INA181A1 reference, RC measurement filter, ADC input and comparator branch.
6. `05_precision_adc` — ADS131M02 reference, SPI interface, local analog/digital decoupling, reference/clock support and unused-channel policy.
7. `06_vibration` — ADXL355 SPI interface, interrupt/test pads, local filtering/decoupling and mechanical-placement note.
8. `07_temperature` — TMP117 I2C interface, pullups, decoupling and thermal-placement note.
9. `08_motor_output` — logic-compatible MOSFET stage, gate resistor/pulldown, flyback/transient clamp and motor connector.
10. `09_safety_io` — E-stop sensing, physical gate inhibit and independent analog hard-trip conditioning.
11. `10_debug_service` — UART, SPI/I2C test pads, programming/service headers and clearly non-actuating telemetry access.

## Frozen global nets

`VIN_12V`, `VIN_PROTECTED`, `MOTOR_12V`, `+5V_SYS`, `+3V3_SYS`, `GND`, `CS_SHUNT_P`, `CS_SHUNT_N`, `CS_AMP_OUT`, `ADC_DRDY`, `ADC_SCLK`, `ADC_MOSI`, `ADC_MISO`, `ADC_CS_N`, `ACC_SCLK`, `ACC_MOSI`, `ACC_MISO`, `ACC_CS_N`, `TEMP_SCL`, `TEMP_SDA`, `FPGA_UART_TX`, `FPGA_UART_RX`, `ANALOG_HARD_TRIP`, `ESTOP_SENSE`, `ESTOP_GATE_OK`, `FPGA_LOAD_ENABLE`, `MOTOR_GATE_CMD`.

`MOTOR_GATE_CMD` must be electrically inhibited by `ESTOP_GATE_OK`; software/ML/telemetry cannot bypass this relationship.

## Capture rules

- Every connector pin receives a label and electrical role.
- Every IC receives local decoupling footprints per vendor guidance before ERC sign-off.
- Kelvin shunt sense traces are named separately from motor-current copper.
- Analog ground-return decisions are reviewed as current paths, not by adding arbitrary split-ground symbols.
- No unverified Tang Nano header pin number is committed as final.
- DNP/option footprints are explicit in BOM fields.
