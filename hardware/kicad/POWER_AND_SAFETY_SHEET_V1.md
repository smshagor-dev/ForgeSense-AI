# Power and Safety Schematic Definition

This file is the capture contract for the ForgeSense low-voltage carrier/reference schematic. It converts the machine-readable baselines into explicit nets and connections. Values are engineering starting points, not certified machine limits.

## Protected 12 V entry

```text
J_PWR
  |
F1 5 A
  |
SMBJ15A TVS
  |
TPS259470L eFuse
  |
VIN_12V_PROTECTED
```

TPS259470L uses 470 kOhm / 36 kOhm / 36 kOhm for approximately 9.03 V UVLO and 18.07 V OVLO, 825 Ohm RILM for approximately 4.04 A current limit, 12 nF ITIMER for approximately 10.1 ms overcurrent blanking, and 3.3 nF dVdt for an approximate 19.8 ms rise to 12 V.

Reference intervention ordering is:

```text
~3.47 A analog motor hard trip
        <
~4.04 A eFuse input current limit
        <
5 A passive fuse
```

The eFuse fault output is diagnostic only. It must never create a motor-enable path.

## Power conversion

`VIN_12V_PROTECTED` feeds TPS54202. The 5 V network uses 10 uF plus 0.1 uF input decoupling, 0.1 uF bootstrap, 15 uH inductance, two 22 uF output capacitors, 100 kOhm / 13.3 kOhm feedback, and 75 pF feed-forward.

TPS7A2033 creates `+3V3_QUIET` for the precision sensing domain with 2.2 uF input and output capacitors. Motor and gate-driver current must not return through this quiet sensing ground path.

## Current measurement and independent trip

Motor return current passes through a 15 mOhm Kelvin shunt. INA181A1 at 20 V/V produces:

`CS_OUT = I_MOTOR * 0.015 * 20`

At 3.2 A, `CS_OUT` is 0.960 V and shunt dissipation is approximately 0.154 W. This keeps the reference operating point at 80% of the ADS131M02 gain-1 nominal positive full-scale range of 1.2 V.

TLV3201 compares `CS_OUT` against `CS_TRIP_REF`. The divider is 23.2 kOhm from 3.3 V to the node and 10.7 kOhm from the node to GND, giving approximately 1.042 V and an ideal reference trip near 3.47 A. Comparator hysteresis has a PCB footprint but remains DNI until measured switching noise defines the required band.

`ANALOG_HARD_TRIP` routes directly to the FPGA deterministic hard-trip input, not through ESP32-S3.

## Precision ADC support

ADS131M02IPWR uses `+3V3_QUIET` for AVDD and DVDD.

- AVDD: local 1 uF to AGND;
- DVDD: local 1 uF to DGND;
- CAP: 220 nF to DGND;
- reference: internal;
- master clock: 8.192 MHz SiT8924 LVCMOS reference;
- FPGA SPI timing: CPOL=0, CPHA=1;
- selected word length: 24 bits;
- selected reference rate: 1 kSPS;
- source damping: 33 Ohm starting footprints on SCLK and MOSI;
- channel 0: `CS_OUT` through 1 kOhm / 100 nF filter;
- channel 1: reserved analog service input by default;
- output CRC must validate before conversion data are accepted.

## Vibration support

ADXL355BEZ uses 3.3 V VSUPPLY and VDDIO with internal 1.8 V regulators. Local 1 uF + 0.1 uF bypass is provided at the relevant domains and both internal LDO outputs retain 100 kOhm discharge resistors.

SPI starts at 2 MHz, mode 0. The selected configuration uses FILTER `0x02`, RANGE `0x03`, measurement POWER_CTL `0x00`, and DRDY-driven 9-byte X/Y/Z acquisition. Identity and configuration readback must pass before measurement data are marked healthy.

## Temperature support

TMP117AIDRVR uses 3.3 V with 0.1 uF local bypass and ADD0 tied to GND. `TEMP_I2C_SCL`, `TEMP_I2C_SDA`, and `TEMP_ALERT` use 4.99 kOhm pull-ups to `+3V3_QUIET` as the reference starting point.

FPGA acquisition checks device ID `0x0117` before publishing normal temperature measurements. TMP117 ALERT remains diagnostic and does not replace the normalized FPGA temperature hard-limit path.

## Motor gate path

UCC27511A is powered from `+5V_LOGIC`.

- `IN+` receives `FPGA_LOAD_ENABLE`;
- `IN-` receives `ESTOP_INHIBIT_5V`;
- output drive uses 22 Ohm turn-on and 4.7 Ohm turn-off starting resistors;
- CSD18540Q5B is the 60 V low-side N-MOSFET;
- 100 kOhm gate-to-source pulldown guarantees default-off bias;
- STPS5L60U is the initial 60 V / 5 A flyback reference.

## Normally-closed E-stop

A 10 kOhm pull-up drives `ESTOP_INHIBIT_5V` high when the normally-closed loop is opened by button actuation or cable failure. UCC27511A therefore disables the motor gate without waiting for FPGA logic. SN74LVC1G17 buffers the same inhibit state into `FPGA_ESTOP_SENSE` for observability.

## Capture and layout constraints

- use `component_packages_v1.csv` for package/MPN information;
- use `net_endpoints_v1.csv` for endpoint/freeze state;
- Kelvin-route both shunt sense traces;
- keep motor-current copper out of sense returns;
- keep TPS54202 SW loop away from `CS_OUT`, ADS131M02, TMP117, ADXL355, E-stop, and hard-trip nets;
- place UCC27511A beside the MOSFET and minimize gate-loop area;
- keep `+3V3_QUIET` free of motor/gate-driver return currents;
- do not freeze unresolved Tang Nano application pins before exact board-revision verification.

## Evidence boundary

Repository checks can validate formulas, topology contracts, selected register values, package selections, and cross-file consistency before hardware exists. They cannot establish EMC, thermal margin, connector suitability, surge compliance, trip tolerance under switching noise, or functional-safety compliance without physical measurement and qualification.
