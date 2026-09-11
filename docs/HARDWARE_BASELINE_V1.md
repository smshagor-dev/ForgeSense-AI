# Hardware Baseline V1

## Purpose

`HW-BL-004` is the current component-backed schematic baseline for the ForgeSense low-voltage reference platform. It is detailed enough to drive schematic capture, BOM review, analytical checks, selected-device acquisition RTL, physical development-board wiring, and later PCB layout.

This is engineering reference material. It is not certification evidence and does not establish safe limits for an arbitrary motor or industrial machine.

## Compute

- FPGA: Sipeed Tang Nano 9K, `GW1NR-LV9QN88PC6/I5`, 27 MHz onboard clock.
- Edge processor: ESP32-S3-DevKitC-1.
- FPGA/ESP32 transport: UART 115200 8N1.
- ESP32 GPIO17 is U1TXD and GPIO18 is U1RXD in the development-board profile.
- Tang Nano external application mapping is frozen in `hardware/profiles/interconnect_v1.json` revision `INT-002` against the official Sipeed schematic/pin map. Physical bench validation is still pending.

## Tang Nano 9K physical interconnect

The application wiring uses J5 3.3 V header pins while deliberately avoiding the populated TF-card signals on FPGA pins 36-39, the onboard BL702 UART pins 17/18, and external BANK3 1.8 V pins 79-86.

The frozen map is:

| Function | Header | FPGA pin |
| --- | --- | ---: |
| ESP32 TX -> FPGA RX | J5-5 | 25 |
| FPGA TX -> ESP32 RX | J5-6 | 26 |
| Analog hard trip | J5-7 | 27 |
| E-stop sense | J5-8 | 28 |
| Load enable | J5-9 | 29 |
| Recovery request | J5-10 | 30 |
| TMP117 SCL | J5-11 | 33 |
| TMP117 SDA | J5-12 | 34 |
| ADXL355 CS_N | J5-13 | 40 |
| ADXL355 SCLK | J5-14 | 35 |
| ADXL355 MOSI | J5-15 | 41 |
| ADXL355 MISO | J5-16 | 42 |
| ADXL355 DRDY | J5-17 | 51 |
| ADS131M02 CS_N | J5-18 | 53 |
| ADS131M02 SCLK | J5-19 | 54 |
| ADS131M02 DIN | J5-20 | 55 |
| ADS131M02 DOUT | J5-21 | 56 |
| ADS131M02 DRDY_N | J5-22 | 57 |

The onboard 27 MHz oscillator is FPGA pin 52. Onboard S2 is FPGA pin 4 in the 1.8 V bank and is used only as the local reset input. Pins shared with the RGB header are valid only when no RGB panel is attached.

The authoritative constraints are `fpga/constraints/tang_nano_9k.cst` and `fpga/constraints/tang_nano_9k.sdc`. `make tang-pin-check` cross-checks those files against the machine-readable interconnect profile and physical top-level wrapper.

## Protected 12 V entry

```text
J_PWR
  -> 5 A fuse
  -> SMBJ15A TVS
  -> TPS259470L eFuse
  -> VIN_12V_PROTECTED
```

Reference TPS259470L configuration:

- UVLO: approximately 9.03 V using 470 kOhm / 36 kOhm / 36 kOhm divider;
- OVLO: approximately 18.07 V using the same divider string;
- current limit: approximately 4.04 A using 825 Ohm RILM;
- overcurrent blanking: approximately 10.1 ms using 12 nF ITIMER;
- slew: approximately 0.606 V/ms using 3.3 nF dVdt, about 19.8 ms to 12 V.

Protection ordering remains intentionally layered:

```text
~3.47 A independent analog motor trip
< ~4.04 A eFuse input current limit
< 5 A passive fuse
```

## Power conversion

TPS54202DDCR converts the protected 12 V rail to `+5V_LOGIC`. The starting network uses a 15 uH inductor, 10 uF plus 0.1 uF input decoupling, 0.1 uF bootstrap capacitor, two 22 uF output capacitors, 100 kOhm / 13.3 kOhm feedback, and a 75 pF feed-forward capacitor.

TPS7A2033PDBVR creates `+3V3_QUIET` from 5 V for the precision sensing domain with 2.2 uF input and output ceramics.

## Current sensing

The selected ADS131M02 input range required the current front end to move to a 15 mOhm Kelvin shunt while retaining INA181A1 at 20 V/V.

At 3.2 A:

```text
Vshunt = 3.2 A x 0.015 Ohm = 0.048 V
CS_OUT = 0.048 V x 20 = 0.960 V
Pshunt = 3.2^2 x 0.015 = 0.154 W
```

ADS131M02 gain-1 nominal differential full scale is +/-1.2 V, so the 3.2 A reference point uses 80% of the positive full-scale range before measured gain/offset calibration.

The BOM retains at least 1 W shunt capability for thermal margin and transient testing; final rating remains subject to physical validation.

## Independent analog trip

TLV3201AIDBVR compares `CS_OUT` against a 23.2 kOhm / 10.7 kOhm divider reference of approximately 1.042 V. With the 15 mOhm shunt and 20 V/V gain, the ideal threshold is approximately 3.47 A.

Comparator hysteresis remains DNI until switching-noise measurement supports a value. `ANALOG_HARD_TRIP` feeds the FPGA deterministic safety path and is never routed through ESP32-S3.

## Motor switch and physical E-stop

UCC27511ADBVR is the 5 V gate driver. `IN+` receives `FPGA_LOAD_ENABLE`; `IN-` receives the independent active-high `ESTOP_INHIBIT_5V`.

The E-stop is a normally-closed loop. Healthy wiring pulls the inhibit low. Button actuation or cable-open releases the node, a 10 kOhm pull-up drives it high, and the driver is disabled before any clocked FPGA response is required.

CSD18540Q5B is the 60 V low-side N-MOSFET reference. Starting gate resistors are 22 Ohm turn-on and 4.7 Ohm turn-off, with a 100 kOhm gate pulldown. STPS5L60U is the initial 60 V / 5 A flyback reference.

## Precision ADC support

ADS131M02IPWR is the 24-bit two-channel simultaneous-sampling ADC reference.

- AVDD = 3.3 V with 1 uF local decoupling;
- DVDD = 3.3 V with 1 uF local decoupling;
- CAP = 220 nF to DGND;
- internal voltage reference;
- SiT8924 8.192 MHz LVCMOS master clock;
- FPGA SPI timing CPOL=0, CPHA=1;
- selected communication word length: 24 bits;
- selected reference output rate: 1 kSPS;
- output CRC validation is mandatory before conversion data are published;
- channel 0 receives `CS_OUT` through the 1 kOhm / 100 nF measurement filter.

## Vibration support

ADXL355BEZ is the vibration reference.

- 3.3 V VSUPPLY and VDDIO;
- SPI mode 0 at a 2 MHz starting clock;
- +/-8 g reference range;
- 1 kHz reference output-data rate;
- identity registers and configuration readback are checked before `device_ok`;
- DRDY drives the X/Y/Z burst acquisition path.

The current reference wrapper feeds Z-axis milli-g samples into the existing RMS path. Axis/vector selection remains subject to physical mounting characterization.

## Temperature support

TMP117AIDRVR uses 3.3 V, 0.1 uF local bypass, ADD0 tied to GND, and 4.99 kOhm pull-ups for SCL/SDA/ALERT.

FPGA acquisition checks device ID `0x0117` before accepting measurement requests. TMP117 ALERT remains diagnostic and does not replace normalized FPGA temperature hard limits.

## Selected-device RTL

Register-level acquisition is documented in `SENSOR_DEVICE_DRIVERS.md`. The selected-device composition connects TMP117, ADXL355, and ADS131M02 to the existing vendor-neutral sensor frontend and deterministic safety stack.

Shared fixed-point conversion/scaling rules live in `fpga/rtl/sensing/sensor_device_math_pkg.vhd` and are covered by a self-checking VHDL testbench so the selected-device wrapper and individual controllers cannot silently drift onto different arithmetic.

## Schematic source of truth

The following files must agree:

- `hardware/profiles/hardware_baseline_v1.json`
- `hardware/profiles/power_entry_v1.json`
- `hardware/profiles/sensor_support_v1.json`
- `hardware/profiles/sensor_devices_v1.json`
- `hardware/profiles/reference_circuit_v1.json`
- `hardware/profiles/interconnect_v1.json`
- `hardware/kicad/schematic_contract_v1.json`
- `hardware/kicad/POWER_AND_SAFETY_SHEET_V1.md`
- `hardware/kicad/component_packages_v1.csv`
- `hardware/kicad/net_endpoints_v1.csv`
- `hardware/bom/preliminary_bom_v1.csv`

Run:

```bash
make hardware-check
```

The checks prevent silent drift across protection ordering, current transfer, ADC headroom, trip threshold, serial timing assumptions, selected sensor identities/registers, E-stop policy, package manifest, and the frozen Tang Nano 9K physical pin map.
