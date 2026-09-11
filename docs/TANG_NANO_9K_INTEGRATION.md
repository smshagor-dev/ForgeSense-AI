# Tang Nano 9K Physical Integration

## Scope

This document freezes the ForgeSense development-board wiring for the Sipeed Tang Nano 9K before bench bring-up. It records only mappings verified against the official Sipeed Tang Nano 9K schematic/pin map and keeps electrical bench validation separate from schematic evidence.

Board reference:

- FPGA: `GW1NR-LV9QN88PC6/I5`
- onboard clock: 27 MHz, FPGA pin 52
- onboard S2 reset input: FPGA pin 4, BANK3 1.8 V
- external ForgeSense peripheral wiring: J5 3.3 V header region

Official references:

- `https://wiki.sipeed.com/hardware/en/tang/Tang-Nano-9K/Nano-9K.html`
- `https://dl.sipeed.com/fileList/TANG/Nano%209K/2_Schematic/Tang_Nano_9k_3672_Schematic.pdf`

## Frozen application mapping

| ForgeSense signal | Tang header | FPGA pin | Direction |
| --- | --- | ---: | --- |
| ESP32 TX / FPGA RX | J5-5 | 25 | input |
| FPGA TX / ESP32 RX | J5-6 | 26 | output |
| Analog hard trip | J5-7 | 27 | input |
| E-stop sense | J5-8 | 28 | input |
| Load enable | J5-9 | 29 | output |
| Recovery request | J5-10 | 30 | input |
| TMP117 SCL | J5-11 | 33 | bidirectional open-drain |
| TMP117 SDA | J5-12 | 34 | bidirectional open-drain |
| ADXL355 CS_N | J5-13 | 40 | output |
| ADXL355 SCLK | J5-14 | 35 | output |
| ADXL355 MOSI | J5-15 | 41 | output |
| ADXL355 MISO | J5-16 | 42 | input |
| ADXL355 DRDY | J5-17 | 51 | input |
| ADS131M02 CS_N | J5-18 | 53 | output |
| ADS131M02 SCLK | J5-19 | 54 | output |
| ADS131M02 DIN | J5-20 | 55 | output |
| ADS131M02 DOUT | J5-21 | 56 | input |
| ADS131M02 DRDY_N | J5-22 | 57 | input |

The J5 lines selected above are in 3.3 V banks. Pins 36-39 are intentionally not used because they are connected to the populated TF-card interface. FPGA pins 17/18 are intentionally not used for the external ESP32 link because they are routed to the onboard BL702 USB-UART path. External BANK3 pins 79-86 are 1.8 V and are excluded from the 3.3 V ForgeSense wiring.

Some selected J5 signals are shared with the RGB display connector. The ForgeSense development wiring therefore assumes no RGB panel is attached at the same time.

## Reset and asynchronous safety inputs

`forgesense_tang_nano_9k_top.vhd` uses the onboard S2 input only as local FPGA reset. Reset deassertion is synchronized to the 27 MHz clock.

`ANALOG_HARD_TRIP`, `ESTOP_SENSE`, and `RECOVERY_REQUEST` are asynchronous external observations and pass through two-flop synchronizers before entering the clocked platform logic.

The physical E-stop gate-inhibit circuit remains independent of the FPGA clock and is not replaced by the synchronized `ESTOP_SENSE` observation.

## I2C electrical behavior

TMP117 SCL/SDA are implemented as open-drain `inout` ports. The FPGA drives only logic low or high-impedance. Pull-ups are external and remain defined by the hardware baseline at 4.99 kOhm reference value.

## Constraints

Physical constraints:

`fpga/constraints/tang_nano_9k.cst`

Timing constraint:

`fpga/constraints/tang_nano_9k.sdc`

The 27 MHz input is constrained to a 37.037 ns period.

Run the static consistency gate with:

```bash
make tang-pin-check
```

The checker rejects duplicate pin allocation, reuse of TF-card/onboard-UART/BANK3 reserved pins, voltage-standard drift, interconnect-profile mismatch, missing synchronizers, or loss of the open-drain I2C semantics.

## Gowin build entry point

With a compatible Gowin installation and license available:

```bash
make gowin-build
```

This calls `gw_sh fpga/scripts/tang_nano_9k_build.tcl` and targets `forgesense_tang_nano_9k_top`.

No Gowin synthesis/place-and-route/timing-closure result is claimed until that command is executed successfully with the selected tool version and the reports are retained.

## Evidence boundary

The following are now frozen as design inputs:

- physical FPGA pin selection;
- IO voltage standard selection;
- 27 MHz timing constraint;
- top-level physical wrapper;
- selected sensor/control wiring topology;
- build entry point.

The following still require physical or implementation evidence:

- successful Gowin synthesis and place-and-route;
- timing closure;
- actual UART/SPI/I2C signal integrity;
- pull-up/rise-time measurement;
- hard-trip/E-stop electrical behavior at the connector;
- sensor-board bring-up;
- motor-output bench validation.
