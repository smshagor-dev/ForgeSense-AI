# FPGA Deterministic Safety Core

The synthesizable RTL now implements:

- hard temperature/vibration/current limits;
- sensor-validity fail-safe handling;
- communication watchdog;
- deterministic safety state machine;
- fault latching and controlled recovery;
- validated-intelligence freshness gate;
- output enable only in permitted states;
- selected TMP117, ADXL355, and ADS131M02 acquisition controllers;
- Tang Nano 9K physical-board integration.

`intelligence_gate.vhd` consumes already-decoded protocol fields. Byte-stream framing remains separate so framing faults cannot silently alter the safety-state-machine contract.

The physical development-board top is:

`rtl/top/forgesense_tang_nano_9k_top.vhd`

Constraints:

- `constraints/tang_nano_9k.cst`
- `constraints/tang_nano_9k.sdc`

Static pin verification:

```bash
make tang-pin-check
```

Gowin command-line build, when a compatible licensed installation is available:

```bash
make gowin-build
```

The build entry calls `gw_sh fpga/scripts/tang_nano_9k_build.tcl` and targets `GW1NR-LV9QN88PC6/I5`.

Numeric hard limits remain provisional simulation defaults and must be replaced by measured electrical/mechanical requirements before physical output control is treated as validated.
