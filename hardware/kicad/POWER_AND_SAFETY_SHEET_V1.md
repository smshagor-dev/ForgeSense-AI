# Power and Safety Schematic Definition

This file is the capture contract for the first ForgeSense carrier/reference schematic. It converts the machine-readable hardware baseline into explicit nets and component connections. Values are engineering starting points, not certified machine limits.

## Power conversion

`VIN_12V_PROTECTED` feeds TPS54202. The 5 V network follows TI's 5 V reference design starting point:

- input: 10 uF bulk plus 0.1 uF local ceramic;
- bootstrap: 0.1 uF from BOOT to SW;
- inductor: 15 uH;
- output: two 22 uF ceramic capacitors;
- feedback: 100 kOhm upper, 13.3 kOhm lower, 75 pF feed-forward;
- output net: `+5V_LOGIC`, design load budget 2 A maximum device rating.

`+5V_LOGIC` powers the development compute modules and UCC27511A. A TPS7A2033 produces `+3V3_QUIET` for the ADC and low-noise sensing domain. Start with 2.2 uF input and output ceramics; the LDO requires at least 1 uF output capacitance.

## Current measurement and independent trip

Motor return current passes through a 25 mOhm Kelvin shunt. INA181A1 at 20 V/V produces:

`CS_OUT = I_MOTOR * 0.025 * 20`

At 3.2 A, `CS_OUT` is 1.60 V.

TLV3201 compares `CS_OUT` against `CS_TRIP_REF`. The reference divider is 47.5 kOhm from 3.3 V to the node and 52.3 kOhm from the node to GND, giving approximately 1.73 V. That corresponds to an ideal reference trip near 3.46 A. Comparator hysteresis has a PCB footprint but is DNI until switching-noise measurements define the required band.

The comparator output is `ANALOG_HARD_TRIP`, routed to the FPGA deterministic hard-trip input. It is not routed through the ESP32-S3.

## Motor gate path

UCC27511A is powered from `+5V_LOGIC`.

- `IN+` receives `FPGA_LOAD_ENABLE`.
- `IN-` receives `ESTOP_INHIBIT_5V`.
- output drive uses separate starting resistors: 22 Ohm turn-on and 4.7 Ohm turn-off.
- CSD18540Q5B is the low-side N-MOSFET.
- 100 kOhm gate-to-source pulldown guarantees default-off bias.
- STPS5L60 is the initial flyback diode across the motor branch.

The MOSFET is a 60 V part with RDS(on) specified at 4.5 V gate drive, so the 5 V driver avoids relying on an unspecified 3.3 V RDS(on).

## Normally-closed E-stop

The E-stop cable is a normally-closed loop. A 10 kOhm pull-up drives `ESTOP_INHIBIT_5V` high when the loop is opened by either button actuation or cable failure. Healthy closed contact pulls the node low.

UCC27511A can only drive its output high when `IN+` is high and `IN-` is low. Therefore a high `ESTOP_INHIBIT_5V` disables the motor gate without waiting for FPGA logic.

The same inhibit node enters SN74LVC1G17 powered at 3.3 V. Its over-voltage-tolerant input accepts the 5 V inhibit node and produces `FPGA_ESTOP_SENSE` at the FPGA logic rail. This provides state observability without making the hardware gate inhibit dependent on the FPGA.

## Layout constraints

- Kelvin-route both shunt sense traces; do not share motor-current copper with sense return.
- Keep TPS54202 switching loop compact and away from `CS_OUT`, ADS131M02, TMP117, and ADXL355.
- Place UCC27511A beside the MOSFET and minimize gate-loop area.
- Place flyback current loop beside the motor connector and switch.
- Treat `+3V3_QUIET` as a sensing rail; do not return motor or gate-driver currents through it.
- Route `ANALOG_HARD_TRIP` and E-stop sense away from SW/gate nodes.
- No unresolved Tang Nano external signal pin may be committed to PCB/CST until verified against the exact board revision.

## Evidence boundary

The repository can validate formulas, topology contracts, and cross-file consistency before hardware exists. It cannot establish EMC, thermal margin, connector suitability, trip tolerance under noise, or functional-safety compliance without physical measurements and the applicable certification process.
