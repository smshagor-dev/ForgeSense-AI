# Physical Bring-Up Procedure

## Purpose

This procedure turns the current pre-hardware reference into a controlled bench-validation sequence. It deliberately separates schematic/RTL intent from measured evidence.

The procedure is for the low-voltage 5-12 V research setup. It does not cover mains wiring or industrial functional-safety certification.

## Required source files

- `hardware/bringup/tang_nano_9k_harness_v1.csv`
- `hardware/bringup/test_points_v1.json`
- `hardware/bringup/bench_record_schema_v1.json`
- `hardware/bringup/bench_record_template_v1.json`
- `hardware/bringup/WIRING_ASSEMBLY.md`
- `fpga/constraints/tang_nano_9k.cst`
- `fpga/constraints/tang_nano_9k.sdc`
- `fpga/rtl/top/forgesense_tang_nano_9k_smoke_top.vhd`

Run the static package gate first:

```bash
make bringup-check
```

## Stage 0 — unpowered inspection

Motor supply remains disconnected.

Before applying power:

1. Confirm the Tang Nano board revision and record it.
2. Confirm the ESP32-S3 development-board revision.
3. Confirm no RGB panel is attached to the Tang Nano shared header.
4. Verify the harness against `tang_nano_9k_harness_v1.csv` wire by wire.
5. Verify logic ground continuity.
6. Check for shorts between each powered rail and ground.
7. Confirm the gate-driver inhibit/E-stop hardware path is physically capable of holding the power stage off without FPGA participation.
8. Confirm `LOAD_ENABLE` is not accidentally shorted high.

Acceptance: no unresolved wiring discrepancy and no unexpected low-resistance power-to-ground path.

## Stage 1 — logic-only power

Keep the motor supply disconnected and keep the external power stage inhibited.

Power the Tang Nano 9K and ESP32-S3 development boards only. Connect common logic ground and the UART pair from the harness manifest. Do not tie the two development-board 5 V rails together as part of the smoke test.

Acceptance:

- neither board shows abnormal heating;
- USB current draw is stable for the specific boards in use;
- `TP_LOAD_EN` measures logic low before and after programming the smoke image.

Record the actual observed currents rather than copying expected values from documentation.

## Stage 2 — first-bitstream smoke image

Build/program `forgesense_tang_nano_9k_smoke_top`.

The smoke image has intentionally reduced authority:

- `LOAD_ENABLE` is hard-tied low;
- TMP117 I2C pins are high-impedance;
- ADXL355 and ADS131M02 chip selects are inactive;
- sensor clocks are idle;
- FPGA UART periodically sends `0x55` while idle;
- a received UART byte is echoed back.

Acceptance:

- `TP_LOAD_EN` remains low continuously;
- ADXL355 and ADS131M02 CS_N remain high;
- SCLK outputs remain low;
- TMP117 SCL/SDA are not actively driven low by the FPGA;
- `0x55` heartbeat is visible on `TP_UART_TX` approximately once per second.

If any actuator-related output is unexpectedly active, stop the test and do not proceed.

## Stage 3 — bidirectional UART

Use stop-and-wait traffic for the smoke image: transmit one byte from ESP32-S3 and wait for the echo before transmitting another.

Reference check:

```text
ESP32 -> FPGA: A6
FPGA  -> ESP32: A6
```

Acceptance:

- byte value matches;
- UART is 115200 8N1;
- no framing error is observed on the logic analyzer;
- repeated single-byte transactions are stable;
- `LOAD_ENABLE` remains low throughout.

## Stage 4 — safety observation wiring

Still keep the motor power stage physically inhibited.

Check the connector-side states of:

- `ANALOG_HARD_TRIP`;
- `ESTOP_SENSE`;
- `RECOVERY_REQUEST`;
- `LOAD_ENABLE`.

Verify the normally-closed E-stop hardware inhibit independently of FPGA logic. The physical inhibit must disable the gate-driver path even if FPGA firmware/RTL is absent or incorrect.

Acceptance:

- healthy and fault states match the documented polarities;
- opening/pressing the E-stop changes the physical inhibit path as designed;
- the smoke image still cannot energize the load command.

## Stage 5 — sensor rails and buses, one device at a time

Do not connect all sensors at once for first bring-up. Add one device, verify it, power down, then add the next.

### TMP117

Check:

- 3.3 V local supply;
- SCL/SDA idle-high level;
- rise time and absence of bus contention;
- device identity `0x0117` when the production image is later used.

### ADXL355

Check:

- 3.3 V supply/I/O;
- CS_N idle high;
- mode-0 clock polarity/phase;
- DRDY activity after configuration;
- identity/configuration readback before trusting samples.

### ADS131M02

Check:

- AVDD/DVDD support rails;
- 8.192 MHz master clock;
- CS_N idle high;
- CPOL=0/CPHA=1 SPI timing;
- DRDY_N activity;
- output CRC acceptance before samples are trusted.

Acceptance: each device independently reaches stable electrical signaling with no unexplained heating, contention, or rail collapse.

## Stage 6 — analog current-sense path

Keep the motor disconnected or use a controlled low-current test source/load appropriate to the bench setup.

Measure and record:

- `TP_CS_OUT` at zero current;
- `TP_TRIP_REF`;
- applied current versus `CS_OUT` at several safe points;
- comparator output transition point;
- observed noise near the comparator threshold.

The schematic reference predicts approximately:

- `CS_OUT = 0.960 V` at 3.2 A for the 15 mOhm / 20 V/V path;
- trip reference approximately `1.042 V`;
- ideal comparator trip near `3.47 A`.

These are design references, not measured results. The bench record must contain the real measurements.

## Stage 7 — deterministic hard-trip and E-stop bench checks

Use a current-limited low-voltage setup. Keep a direct means of removing power available.

Hard-trip acceptance:

- comparator assertion is observed at the expected test point;
- FPGA hard-critical observation changes appropriately under the production image;
- `LOAD_ENABLE` is removed/latches safe according to the safety design;
- ML/ESP32 state is not required for the hard protection to occur.

E-stop acceptance:

- physical gate-driver inhibit disables the drive path immediately at the hardware level;
- FPGA observes the E-stop fault separately;
- release alone does not create an uncontrolled restart;
- recovery follows the explicit recovery policy.

## Stage 8 — motor-path bring-up

Proceed only after the previous recorded checks pass.

Use the low-voltage reference motor/fan and a current-limited supply. Start below the intended maximum operating current and observe:

- supply current;
- MOSFET gate waveform;
- drain/flyback transient;
- shunt/current-sense waveform;
- 5 V and 3.3 V rail disturbance;
- UART/SPI/I2C integrity during switching;
- temperature rise of shunt, MOSFET, flyback device, and regulators.

Do not infer safe operating limits from the simulation defaults. Bench evidence must drive later threshold decisions.

## Evidence recording

Copy `hardware/bringup/bench_record_template_v1.json` for each run and fill it from measurements.

A retained record should identify:

- exact repository commit;
- FPGA board revision;
- ESP32 board revision;
- sensor-board revision;
- programmed top/image and artifact SHA-256;
- instruments and calibration status;
- bench-supply settings and measured idle current;
- every check result;
- waveform/log/photo file hashes when retained.

A test that was not performed is `NOT_RUN`/`INCOMPLETE`, not PASS.

## Stop conditions

Stop and remove power if any of the following occurs:

- unexpected rail collapse or excessive current;
- unexpected component heating;
- `LOAD_ENABLE` high during the smoke image;
- bus contention or abnormal logic voltage;
- repeated CRC/identity/configuration faults with known-good wiring;
- E-stop hardware inhibit fails to remove drive authority;
- hard-trip path does not remove deterministic drive authority as designed;
- unexpected motor-output switching while the test calls for an inhibited stage.
