# Power and Safety Schematic Definition

This file is the capture contract for the ForgeSense low-voltage carrier/reference schematic. It converts the machine-readable baselines into explicit nets and connections. Values are engineering starting points, not certified machine limits.

## Protected 12 V entry

The input chain is intentionally layered:

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

TPS259470L is the active protected-entry device. The reference network uses 470 kOhm / 36 kOhm / 36 kOhm for approximately 9.03 V UVLO and 18.07 V OVLO, 825 Ohm RILM for approximately 4.04 A current limit, 12 nF ITIMER for approximately 10.1 ms overcurrent blanking, and 3.3 nF dVdt for an approximate 19.8 ms rise to 12 V.

The selected SMBJ15A reference has 15 V reverse standoff and a 24.4 V specified maximum clamp point, below the eFuse 28 V absolute maximum at that reference condition. This is a coordination starting point only; cable/source inductance and real pulse energy require measurement before any surge-compliance claim.

Reference intervention ordering is:

```text
~3.46 A analog motor hard trip
        <
~4.04 A eFuse input current limit
        <
5 A passive fuse
```

The eFuse fault output is diagnostic only. It must never create a motor-enable path.

## Power conversion

`VIN_12V_PROTECTED` feeds TPS54202. The 5 V network follows the selected 5 V reference starting point:

- input: 10 uF bulk plus 0.1 uF local ceramic;
- bootstrap: 0.1 uF from BOOT to SW;
- inductor: 15 uH;
- output: two 22 uF ceramic capacitors;
- feedback: 100 kOhm upper, 13.3 kOhm lower, 75 pF feed-forward;
- output net: `+5V_LOGIC`, device reference rating 2 A.

`+5V_LOGIC` powers the development compute modules and UCC27511A. TPS7A2033 creates `+3V3_QUIET` for the precision sensing domain with 2.2 uF input and 2.2 uF output starting capacitors.

## Current measurement and independent trip

Motor return current passes through a 25 mOhm Kelvin shunt. INA181A1 at 20 V/V produces:

`CS_OUT = I_MOTOR * 0.025 * 20`

At 3.2 A, `CS_OUT` is 1.60 V and shunt dissipation is 0.256 W.

TLV3201 compares `CS_OUT` against `CS_TRIP_REF`. The divider is 47.5 kOhm from 3.3 V to the node and 52.3 kOhm from the node to GND, giving approximately 1.729 V and an ideal reference trip near 3.46 A. Comparator hysteresis has a PCB footprint but remains DNI until measured switching noise defines the required band.

`ANALOG_HARD_TRIP` routes directly to the FPGA deterministic hard-trip input, not through ESP32-S3.

## Precision ADC support

ADS131M02IPWR uses `+3V3_QUIET` for AVDD and DVDD.

- AVDD: local 1 uF to AGND;
- DVDD: local 1 uF to DGND;
- CAP: 220 nF to DGND for the selected 3.3 V DVDD configuration;
- reference: internal;
- master clock: 8.192 MHz SiT8924 LVCMOS reference;
- SPI source damping: 33 Ohm starting footprints on SCLK and MOSI;
- channel 0: `CS_OUT` through the existing 1 kOhm / 100 nF measurement filter;
- channel 1: reserved analog service and not safety-authoritative by default.

ADC data integrity must retain framing/CRC validation in the acquisition implementation.

## Vibration support

ADXL355BEZ uses 3.3 V VSUPPLY and VDDIO with the internal 1.8 V regulators. Local 1 uF + 0.1 uF bypass is provided at VSUPPLY, VDDIO, V1P8ANA, and V1P8DIG. Both internal LDO outputs receive 100 kOhm discharge resistors.

SPI starts at 2 MHz, mode 0 (`CPOL=0`, `CPHA=0`). A dedicated SCLK is preferred. If the physical bus is shared, the clock must be gated so ADXL355 does not see unrelated clocks while deselected. The ForgeSense raw acquisition target remains 1 kHz and DRDY-driven.

## Temperature support

TMP117AIDRVR uses 3.3 V with 0.1 uF local bypass and ADD0 tied to GND. `TEMP_I2C_SCL`, `TEMP_I2C_SDA`, and `TEMP_ALERT` use 4.99 kOhm pull-ups to `+3V3_QUIET` as the reference starting point. Pull-up values must be revalidated against measured bus capacitance.

TMP117 ALERT is diagnostic. It does not replace the normalized FPGA temperature hard-limit path.

## Motor gate path

UCC27511A is powered from `+5V_LOGIC`.

- `IN+` receives `FPGA_LOAD_ENABLE`;
- `IN-` receives `ESTOP_INHIBIT_5V`;
- output drive uses 22 Ohm turn-on and 4.7 Ohm turn-off starting resistors;
- CSD18540Q5B is the 60 V low-side N-MOSFET;
- 100 kOhm gate-to-source pulldown guarantees default-off bias;
- STPS5L60U is the initial 60 V / 5 A flyback reference.

## Normally-closed E-stop

The E-stop cable is a normally-closed loop. A 10 kOhm pull-up drives `ESTOP_INHIBIT_5V` high when the loop is opened by button actuation or cable failure. Healthy closed contact pulls the node low.

UCC27511A can drive high only when `IN+` is high and `IN-` is low, so a high inhibit disables the motor gate without waiting for FPGA logic. SN74LVC1G17, powered at 3.3 V, buffers the same inhibit state into `FPGA_ESTOP_SENSE` for observability.

## Capture and layout constraints

- Use `component_packages_v1.csv` as the package/MPN manifest; do not invent KiCad footprint IDs before library verification.
- Use `net_endpoints_v1.csv` as the endpoint/freeze-state table.
- Kelvin-route both shunt sense traces and keep motor-current copper out of sense returns.
- Keep TPS54202 SW loop away from `CS_OUT`, ADS131M02, TMP117, ADXL355, E-stop, and hard-trip nets.
- Place UCC27511A beside the MOSFET and minimize gate-loop area.
- Place flyback current loop beside the motor connector and switch.
- Keep `+3V3_QUIET` free of motor and gate-driver return currents.
- Route `ANALOG_HARD_TRIP` and E-stop observation away from SW/gate nodes.
- No unresolved Tang Nano external signal pin may be committed to PCB/CST until verified against the exact board revision.

## Evidence boundary

The repository can validate formulas, topology contracts, package selections, and cross-file consistency before hardware exists. It cannot establish EMC, thermal margin, connector suitability, surge compliance, trip tolerance under switching noise, or functional-safety compliance without physical measurements and the applicable qualification process.
