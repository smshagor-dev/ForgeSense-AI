# Hardware Baseline V1

## Purpose

`HW-BL-003` is the current component-backed schematic baseline for the ForgeSense low-voltage reference platform. It is detailed enough to drive schematic capture, BOM review, analytical checks, and later PCB layout, while deliberately leaving board-revision-dependent FPGA application pins unresolved.

This is engineering reference material. It is not certification evidence and does not establish safe limits for an arbitrary motor or industrial machine.

## Compute

- FPGA: Sipeed Tang Nano 9K, GW1NR-9, 27 MHz onboard clock.
- Edge processor: ESP32-S3-DevKitC-1.
- FPGA/ESP32 transport: UART 115200 8N1.
- ESP32 GPIO17 is U1TXD and GPIO18 is U1RXD in the development-board profile.
- Tang Nano external application pins remain unfrozen until the exact board revision is verified.

## Protected 12 V entry

The input is constrained to a regulated 12 V DC adapter or lab supply for this reference design.

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
- slew: approximately 0.606 V/ms using 3.3 nF dVdt, about 19.8 ms to 12 V;
- reverse-polarity and reverse-current blocking are required by the selected eFuse topology.

SMBJ15A is the input TVS reference. Its selection is a pre-hardware coordination starting point, not a surge-compliance result.

Protection ordering is intentionally layered:

```text
~3.46 A independent analog motor trip
< ~4.04 A eFuse input current limit
< 5 A passive fuse
```

The eFuse does not replace the analog hard-trip or FPGA normalized hard limits.

## Power conversion

### 5 V logic rail

TPS54202DDCR converts the protected 12 V rail to `+5V_LOGIC`. The starting network uses:

- 15 uH inductor;
- 10 uF plus 0.1 uF input decoupling;
- 0.1 uF bootstrap capacitor;
- two 22 uF output capacitors;
- 100 kOhm / 13.3 kOhm feedback divider;
- 75 pF feed-forward capacitor;
- 2 A device reference rating.

### 3.3 V quiet rail

TPS7A2033PDBVR creates `+3V3_QUIET` from 5 V for the precision sensing domain. The starting network uses 2.2 uF input and 2.2 uF output ceramics. Motor and gate-driver current must not return through this rail's sensitive ground path.

## Current sensing

The current path uses a 25 mOhm Kelvin shunt and INA181A1IDBVR at 20 V/V.

At 3.2 A:

```text
Vshunt = 3.2 A x 0.025 Ohm = 0.080 V
CS_OUT = 0.080 V x 20 = 1.600 V
Pshunt = 3.2^2 x 0.025 = 0.256 W
```

The BOM requires at least 1 W and preferably 2 W for the shunt before real thermal validation.

## Independent analog trip

TLV3201AIDBVR compares `CS_OUT` against a 47.5 kOhm / 52.3 kOhm divider reference of approximately 1.729 V. The resulting ideal current threshold is approximately 3.46 A.

Comparator hysteresis is a DNI footprint until motor-switching noise is measured. `ANALOG_HARD_TRIP` feeds the FPGA deterministic safety path and is never routed through ESP32-S3.

## Motor switch and physical E-stop

UCC27511ADBVR is the 5 V gate driver. `IN+` receives `FPGA_LOAD_ENABLE`; `IN-` receives the independent active-high `ESTOP_INHIBIT_5V`.

The E-stop is a normally-closed loop. Healthy wiring pulls the inhibit low. Button actuation or cable-open releases the node, a 10 kOhm pull-up drives it high, and the driver is disabled before any clocked FPGA response is required.

CSD18540Q5B is the 60 V low-side N-MOSFET reference. Starting gate resistors are 22 Ohm turn-on and 4.7 Ohm turn-off, with a 100 kOhm gate pulldown. STPS5L60U is the initial 60 V / 5 A flyback reference.

SN74LVC1G17DBVR buffers the 5 V inhibit state into the 3.3 V FPGA observation domain without placing the hardware gate inhibit under FPGA control.

## Precision ADC support

ADS131M02IPWR is the 24-bit two-channel simultaneous-sampling ADC reference.

- AVDD = 3.3 V with 1 uF local decoupling;
- DVDD = 3.3 V with 1 uF local decoupling;
- CAP = 220 nF to DGND in the selected DVDD configuration;
- internal voltage reference;
- SiT8924 8.192 MHz LVCMOS master-clock reference;
- channel 0 receives `CS_OUT` through the current measurement filter;
- SPI source-damping footprints start at 33 Ohm;
- data integrity remains protected by the acquisition framing/CRC rules.

## Vibration support

ADXL355BEZ is the vibration reference.

- 3.3 V VSUPPLY and VDDIO;
- internal 1.8 V regulators;
- 1 uF + 0.1 uF local bypass on the relevant supply/LDO domains;
- 100 kOhm discharge resistors on V1P8ANA and V1P8DIG;
- SPI mode 0;
- 2 MHz starting clock, below the 10 MHz device maximum;
- dedicated SCLK preferred; shared bus requires gated SCLK;
- ±8 g reference range;
- ForgeSense raw acquisition target: 1 kHz;
- at least 200 ms complete-discharge reference before power restart in the bring-up procedure.

## Temperature support

TMP117AIDRVR uses 3.3 V, 0.1 uF local bypass, and ADD0 tied to GND. SCL, SDA, and ALERT start with 4.99 kOhm pull-ups to `+3V3_QUIET`; final values require bus-capacitance measurement.

TMP117 ALERT is a diagnostic signal and does not replace the normalized FPGA temperature hard-limit path.

## Package and net manifests

The schematic capture must use:

- `hardware/kicad/component_packages_v1.csv` for verified manufacturer package/orderable-MPN information;
- `hardware/kicad/net_endpoints_v1.csv` for net source/destination, voltage domain, safety classification, and freeze state.

Manufacturer package information is frozen, but KiCad library footprint identifiers are deliberately not guessed. Footprint binding remains pending until checked against the actual installed KiCad library.

## Schematic source of truth

The following files must agree:

- `hardware/profiles/hardware_baseline_v1.json`
- `hardware/profiles/power_entry_v1.json`
- `hardware/profiles/sensor_support_v1.json`
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

The checker prevents silent drift across protection ordering, rail definitions, current-transfer calculation, trip threshold, E-stop policy, sensor-support networks, package manifest, net freeze state, and development-board UART mapping.
